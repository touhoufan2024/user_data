import argparse
import os

# freqtrade backtesting --config user_data/config.json --strategy SampleStrategy --timeframe 5m --timerange=20240101-  -p BTC/USDT:USDT

# freqtrade backtesting  --userdir ../  --config ../config.json --strategy raindow --timeframe 5m --timerange=20240101-

# const
user_data = "../"

config = user_data + "config.json"




def greet_name(name):
    print(f"Hello, {name}!")


def execute_command(command):
    print(f"Executing command: {command}")


def calculate_sum(a, b):
    result = a + b
    print(f"The sum of {a} and {b} is {result}")


def test():
    cmd = "freqtrade backtesting --userdir {0} --config {1} --strategy raindow --timeframe 5m --timerange=20240101-".format(user_data, config)
    print(cmd)
    os.system(cmd)

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

    # source
    os.system("source ../..//.venv/bin/activate")
    os.system("export https_proxy=http://127.0.0.1:2080 http_proxy=http://127.0.0.1:2080 all_proxy=socks5://127.0.0.1:2080")

    # 解析参数
    args = parser.parse_args()

    # 根据参数执行操作
    if args.name:
        greet_name(args.name)

    if args.command:
        execute_command(args.command)

    if args.add:
        calculate_sum(args.add[0], args.add[1])


    if args.test:
        test()




if __name__ == "__main__":
    main()
