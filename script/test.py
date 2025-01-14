import argparse
import os
import subprocess

# freqtrade backtesting --userdir ../ --config ../config.json --strategy raindow --timeframe 5m --timerange=20240101-
# freqtrade download-data  --userdir ../ --config ../config.json  --timerange 20220101- -t 5m 15m 30m


# const
user_data = "../"

config = user_data + "config.json"
common = "--userdir ../ --config ../config.json"

def switch_to_script_directory():
    # 获取脚本的绝对路径
    script_path = os.path.abspath(__file__)
    # 获取脚本所在的目录
    script_dir = os.path.dirname(script_path)
    # 切换到脚本目录
    os.chdir(script_dir)
    print(f"Current working directory switched to: {script_dir}")

def update_data_git_repository():
    """将 data 文件夹更新到 Git 仓库。"""
    try:
        # 检查是否在 Git 仓库中
        subprocess.run(["git", "status"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 添加 data 文件夹的更改
        subprocess.run(["git", "add", "../data"], check=True)
        print("Data folder changes added to staging area.")

        # 提交更改
        commit_message = "Update data folder with new data"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        print("Changes committed to Git repository.")

        # 推送更改到远程仓库
        subprocess.run(["git", "push"], check=True)
        print("Changes pushed to remote repository.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred during Git operations: {e}")
        exit(1)

def run_cmd(cmd):
    print(cmd)
    os.system(cmd)


def webserver():
    cmd = "freqtrade webserver {0}".format(common)
    run_cmd(cmd)


def test(name):
    cmd = "freqtrade backtesting {0} --strategy {1} --timeframe 15m --timerange=20240101-".format(common, name)
    run_cmd(cmd)

def download():
    cmd = "freqtrade download-data {0} --timeframe 5m 15m 30m 1h 2h --timerange=20240101-".format(common)
    run_cmd(cmd)
    update_data_git_repository()

def list():
    cmd = "freqtrade list-strategies {0}".format(common)
    run_cmd(cmd)

def main():
    # 创建解析器
    parser = argparse.ArgumentParser(description="A script to execute commands based on input parameters.")

    # 添加参数
    parser.add_argument("-n", "--name", type=str, help="Provide a name to greet")
    parser.add_argument("-c", "--command", type=str, help="Provide a command to execute")
    parser.add_argument("-a", "--add", nargs=2, type=int, metavar=("A", "B"),
                        help="Provide two numbers to calculate their sum")

    parser.add_argument("--greet", action="store_true", help="Greet the world")
    # parser.add_argument("-t", "--test", action="store_true", help="backtest")
    parser.add_argument("-d", "--download", action="store_true", help="download")
    parser.add_argument("-w", "--webserver", action="store_true", help="webserver")
    parser.add_argument("-l", "--list", action="store_true", help="list")

    parser.add_argument("-t", "--test", nargs="?", const="raindow", default=None,
                        help="Provide a name to greet. Defaults to 'hello' if not specified.")


    switch_to_script_directory()
    # source
    os.system("source ../..//.venv/bin/activate")
    os.system("export https_proxy=http://127.0.0.1:2080 http_proxy=http://127.0.0.1:2080 all_proxy=socks5://127.0.0.1:2080")

    # 解析参数
    args = parser.parse_args()

    if args.test:
        test(args.test)

    if args.download:
        download()

    if args.webserver:
        webserver()

    if args.list:
        list()

if __name__ == "__main__":
    main()
