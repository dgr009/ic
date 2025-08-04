from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="ic",
    version="1.0.0",
    author="SangYun",
    author_email="cruiser594@gmail.com",
    description="A CLI tool for managing infra resources and services.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dgr009/ic",  # 프로젝트 URL이 있다면 수정하세요.
    packages=find_packages(),
    install_requires=[
        "boto3",
        "oci",
        "requests",
        "paramiko",
        "rich",
        "InquirerPy",
        "tqdm",
        "python-dotenv",
        "python-dateutil",
    ],
    entry_points={
        "console_scripts": [
            "ic=ic.cli:main"
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",  # 라이선스 종류에 따라 수정 가능
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
