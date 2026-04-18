import warnings

# requests 对 urllib3 / chardet 组合版本检查较严，与 baidu-aip 并存时常误报；仅屏蔽该条提示
warnings.filterwarnings(
    "ignore",
    message=r".*urllib3.*doesn't match a supported version.*",
)

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
