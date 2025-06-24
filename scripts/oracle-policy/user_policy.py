import oci
import os
from dotenv import load_dotenv
from InquirerPy import inquirer
from rich.console import Console
from rich.tree import Tree
import re

load_dotenv()


def load_config_from_env():
    config_path = os.environ.get("OCI_CONFIG_PATH", os.path.expanduser("~/.oci/config"))
    try:
        return oci.config.from_file(file_location=config_path)
    except Exception as e:
        raise RuntimeError(f"❌ OCI config를 불러오는 데 실패했습니다: {e}")


def select_user_or_group(config):
    identity = oci.identity.IdentityClient(config)
    console = Console()

    # 사용자 및 그룹 목록 가져오기
    users = identity.list_users(config["tenancy"]).data
    groups = identity.list_groups(config["tenancy"]).data

    # 선택지 생성
    user_choices = [f"User: {user.name}" for user in users]
    group_choices = [f"Group: {group.name}" for group in groups]
    choices = user_choices + group_choices

    # 사용자 또는 그룹 선택
    selected_name = inquirer.fuzzy(
        message="📁 사용할 사용자 또는 그룹을 선택하세요:",
        choices=choices
    ).execute()

    console.print(f"선택된 항목: {selected_name}")
    return selected_name


def list_related_policies(selected_name, config):
    identity = oci.identity.IdentityClient(config)
    console = Console()

    show_empty_compartments = os.getenv("SHOW_EMPTY_COMPARTMENTS", "false").lower() == "true"
    tree = Tree(f"[bold green]Selected: {selected_name}[/bold green]")

    user_group_names = set()
    is_user = selected_name.startswith("User:")
    selected_value = selected_name.split(": ")[1]

    if is_user:
        # 사용자가 속한 그룹 이름들을 수집
        users = identity.list_users(config["tenancy"]).data
        user = next((u for u in users if u.name == selected_value), None)
        if user:
            memberships = identity.list_user_group_memberships(compartment_id=config["tenancy"], user_id=user.id).data
            if memberships:
                group_branch = tree.add("[cyan]Groups:[/cyan]")
                for membership in memberships:
                    group = identity.get_group(membership.group_id).data
                    group_branch.add(f"[cyan]{group.name}[/cyan]")
                    user_group_names.add(group.name)

    # Compartment 및 정책 가져오기
    compartments = identity.list_compartments(
        config["tenancy"], compartment_id_in_subtree=True, access_level="ACCESSIBLE"
    ).data
    root_tenancy = identity.get_compartment(config["tenancy"]).data
    compartments.insert(0, root_tenancy)

    for compartment in compartments:
        policies = identity.list_policies(compartment.id).data
        if not policies and not show_empty_compartments:
            continue

        compartment_branch = tree.add(f"[blue]Compartment: {compartment.name}[/blue]")

        for policy in policies:
            matched_statements = []
            for statement in policy.statements:
                if is_user:
                    if any(re.search(rf"\bGROUP {re.escape(group_name)}\b", statement) for group_name in user_group_names):
                        # console.print(f"Matched statement for user: {statement}")
                        matched_statements.append(statement)
                else:
                    group_name = selected_value
                    if re.search(rf"\bGROUP {re.escape(group_name)}\b", statement):
                        # console.print(f"Matched statement for group: {statement}")
                        matched_statements.append(statement)

            if matched_statements:
                policy_branch = compartment_branch.add(f"[dark_orange]Policy: {policy.name}[/dark_orange]")
                for statement in matched_statements:
                    policy_branch.add(f"[bold white]{statement}[/bold white]")

    console.print(tree)


if __name__ == "__main__":
    # ✅ 환경변수에서 config 경로 로드
    config = load_config_from_env()

    # ✅ 사용자 또는 그룹 선택
    selected_name = select_user_or_group(config)

    # ✅ 관련 정책 및 문장 나열
    list_related_policies(selected_name, config)


