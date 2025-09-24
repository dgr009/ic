#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import oci
import re
from rich.console import Console
from rich.table import Table
from rich import box
from common.progress_decorator import progress_bar, ManualProgress
from src.ic.platforms.oci.common.utils import get_compartments

# ─────────────────────────────────────────────────────────────────────────────
# IAM Policy 구문 분석 (기존 oci_info.py 에서 복원)
# ─────────────────────────────────────────────────────────────────────────────
stmt_pat = re.compile(
    r"""^(allow|endorse)\s+      # Action (group 1)
        (.*?)\s+                  # Subject (group 2, non-greedy)
        to\s+
        ([^{\s]+|\{[^\}]+\})\s+   # Verb (group 3, simple like 'read' or complex like '{read, WRITE}' or '{WLP_BOM_READ}')
        # Resource Type is optional - if next word is 'in', then no resource type
        (?:(?!in\s)(\S+)\s+)?     # Resource Type (group 4, optional, negative lookahead for 'in ')
        # Optional Scope: 'in compartment <name/id>' or 'in tenancy'
        # Group 5 captures the content of the scope (e.g., "compartment <name>", "tenancy")
        (?:in\s+(.+?))?           # Scope content (group 5, optional, non-greedy)
        \s*                       # Allow spaces between scope and where, or scope and EOL
        # Optional Condition: 'where <conditions>'
        # Group 6 captures the conditions string
        (?:\s+where\s+(.*))?$    # Condition (group 6, optional, greedy)
    """,
    re.I | re.X,
)

def parse_stmt(stmt: str):
    """IAM Policy 구문을 파싱하여 각 구성 요소를 추출"""
    m = stmt_pat.match(stmt.strip())
    if not m:
        # 정규식 매칭 실패 시 원본 구문을 적절히 분할하여 표시
        stmt_clean = stmt.strip()
        action = "UNKNOWN"
        if stmt_clean.lower().startswith("allow"):
            action = "ALLOW"
            stmt_clean = stmt_clean[5:].strip()
        elif stmt_clean.lower().startswith("endorse"):
            action = "ENDORSE"
            stmt_clean = stmt_clean[7:].strip()
        if " to " in stmt_clean.lower():
            parts = stmt_clean.split(" to ", 1)
            subject = parts[0].strip()
            remaining = parts[1].strip() if len(parts) > 1 else ""
        else:
            subject = stmt_clean[:50] + "..." if len(stmt_clean) > 50 else stmt_clean
            remaining = ""
        verb = remaining[:30] + "..." if len(remaining) > 30 else remaining
        return (action, subject[:40] + "..." if len(subject) > 40 else subject, verb, "UNPARSED", "-", "-")
    
    action, subject, verb, resource, scope_content, condition_text = m.groups()
    
    if verb.startswith("{") and verb.endswith("}"):
        verb_processed = verb
    else:
        verb_processed = verb.strip("{} ").upper()
    
    return (
        action.upper(),
        subject.strip(),
        verb_processed,
        (resource.strip() if resource else "all-resources"),
        (scope_content.strip() if scope_content else "-"),
        (condition_text.strip() if condition_text else "-"),
    )


def add_arguments(parser):
    parser.add_argument("--name", "-n", default=None, help="Policy 이름 필터 (부분 일치)")
    parser.add_argument("--compartment", "-c", default=None, help="컴파트먼트 이름 필터 (부분 일치)")
    # --details 인자는 더 이상 필요 없음. 항상 상세 정보를 표시.

def collect_policies(identity_client, compartments, name_filter=None):
    all_policies = []
    console = Console()
    
    with ManualProgress(f"Collecting IAM policies from {len(compartments)} compartments", total=len(compartments)) as progress:
        for i, comp in enumerate(compartments):
            try:
                policies = identity_client.list_policies(comp.id).data
                matching_policies = []
                for p in policies:
                    if not name_filter or name_filter.lower() in p.name.lower():
                        all_policies.append({"compartment_name": comp.name, "policy_name": p.name, "statements": p.statements, "id": p.id})
                        matching_policies.append(p.name)
                
                progress.update(f"Processed {comp.name} - Found {len(matching_policies)} policies", advance=1)
                
            except oci.exceptions.ServiceError as e:
                if e.status == 404: # Not Found (some compartments like managed paas)
                    progress.update(f"Skipped {comp.name} (not accessible)", advance=1)
                    continue
                console.print(f"[yellow]Service error listing policies in compartment '{comp.name}' ({comp.id}): {e}[/yellow]")
                progress.advance(1)
            except Exception as e:
                console.print(f"[yellow]Could not list policies in compartment '{comp.name}' ({comp.id}): {e}[/yellow]")
                progress.advance(1)
    
    return all_policies

def print_policy_table(console, policy_rows, show_details):
    if not policy_rows:
        console.print("(No Policies)")
        return
    
    policy_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["policy_name"].lower()))
    
    console.print("\n[bold underline]IAM Policies[/bold underline]")
    table = Table(show_lines=False, box=box.SIMPLE_HEAVY, expand=True)
    headers = ["Compartment", "Policy Name", "Action", "Subject", "Verb", "Resource", "Scope", "Condition"]
    
    for h in headers:
        opts = {}
        if h == "Compartment": opts['style'] = "bold magenta"
        elif h == "Policy Name": opts['style'] = "bold cyan"; opts['overflow'] = 'fold'
        table.add_column(h, **opts)

    curr_comp = curr_pol = None
    for row in policy_rows:
        if row["compartment_name"] != curr_comp:
            if curr_comp is not None:
                table.add_section()
            curr_comp = row["compartment_name"]
            curr_pol = None

        if row["policy_name"] != curr_pol :
            curr_pol = row["policy_name"]

        stmts = row.get("statements", [])
        first_statement_in_policy = True

        for stmt_str in stmts:
            if not stmt_str.strip():
                continue
            action, subject, verb, resource, scope, cond = parse_stmt(stmt_str)

            if first_statement_in_policy:
                table.add_row(
                    row["compartment_name"],
                    row["policy_name"],
                    action,
                    subject,
                    verb,
                    resource,
                    scope,
                    cond,
                )
                first_statement_in_policy = False
            else:
                table.add_row(
                    "", "", # 동일 policy 내에서는 이름 생략
                    action,
                    subject,
                    verb,
                    resource,
                    scope,
                    cond,
                )
    
    console.print(table)


@progress_bar("Initializing OCI IAM policy information collection")
def main(args):
    console = Console()
    try:
        config = oci.config.from_file("~/.oci/config", "DEFAULT")
        identity_client = oci.identity.IdentityClient(config)
    except Exception as e:
        console.print(f"[red]OCI 설정 파일 로드 실패: {e}[/red]"); sys.exit(1)

    compartment_filter = args.compartment.lower() if args.compartment else None
    compartments = get_compartments(identity_client, config["tenancy"], compartment_filter, console)
    
    policy_rows = collect_policies(identity_client, compartments, args.name.lower() if args.name else None)
    print_policy_table(console, policy_rows, False) # show_details 인자는 더 이상 사용되지 않음 