import argparse
import os

# freqtrade backtesting --userdir ../ --config ../config.json --strategy raindow --timeframe 5m --timerange=20240101-
# freqtrade download-data  --userdir ../ --config ../config.json  --timerange 20220101- -t 5m 15m 30m


# const
user_data = "../"

config = user_data + "config.json"
common = "--userdir ../ --config ../config.json"


def run_cmd(cmd):
    print(cmd)
    os.system(cmd)


def webserver():
    cmd = "freqtrade webserver {0}".format(common)
    run_cmd(cmd)


def test():
    cmd = "freqtrade backtesting {0} --strategy raindow --timeframe 15m --timerange=20240101-".format(common)
    run_cmd(cmd)

def download():
    cmd = "freqtrade download-data {0} --timeframe 5m 15m 30m 1h --timerange=20240101-".format(common)
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
    parser.add_argument("-t", "--test", action="store_true", help="backtest")
    parser.add_argument("-d", "--download", action="store_true", help="download")
    parser.add_argument("-w", "--webserver", action="store_true", help="webserver")


    # source
    os.system("source ../..//.venv/bin/activate")
    os.system("export https_proxy=http://127.0.0.1:2080 http_proxy=http://127.0.0.1:2080 all_proxy=socks5://127.0.0.1:2080")

    # 解析参数
    args = parser.parse_args()

    if args.test:
        test()

    if args.download:
        download()

    if args.webserver:
        webserver()

if __name__ == "__main__":
    main()
