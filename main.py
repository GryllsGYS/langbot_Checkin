import os
import re
import json
import sqlite3
import calendar
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from pkg.plugin.context import *
from pkg.plugin.events import *
from pkg.platform.types import *

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'checkin.db')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')


def init_db():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS checkins
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id TEXT NOT NULL,
         group_id TEXT NOT NULL,
         checkin_date DATE NOT NULL)
    ''')
    conn.commit()
    conn.close()


def checkin(user_id, group_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute(
        "INSERT INTO checkins (user_id, group_id, checkin_date) VALUES (?, ?, ?)",
        (user_id, group_id, today)
    )
    conn.commit()
    conn.close()
    return True


def graph(user_id, group_id):
    os.makedirs(IMAGES_DIR, exist_ok=True)
    plt.rcParams['font.sans-serif'] = ['SimHei',
                                       'Noto Color Emoji', 'Segoe UI Emoji']
    plt.rcParams['axes.unicode_minus'] = False

    MONTH_NAMES = {
        1: "一月", 2: "二月", 3: "三月", 4: "四月",
        5: "五月", 6: "六月", 7: "七月", 8: "八月",
        9: "九月", 10: "十月", 11: "十一月", 12: "十二月"
    }

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now()
    year = now.year
    month = now.month
    cal = calendar.monthcalendar(year, month)

    c.execute(
        "SELECT checkin_date, COUNT(*) FROM checkins "
        "WHERE user_id = ? AND group_id = ? AND strftime('%Y-%m', checkin_date) = ? "
        "GROUP BY checkin_date",
        (user_id, group_id, f"{year}-{month:02}")
    )
    checkin_counts = {row[0]: row[1] for row in c.fetchall()}
    conn.close()

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axis('off')

    month_name = MONTH_NAMES.get(month, "未知月份")
    ax.set_title(f"{year}年 {month_name}", fontsize=25, pad=20)

    # 加载图片
    deer_image_path = os.path.join(BASE_DIR, 'deer.jpg')
    deer_image = mpimg.imread(deer_image_path)

    # 绘制表格
    for i, week in enumerate(cal):
        for j, day in enumerate(week):
            if day == 0:
                continue  # 跳过空白格子

            # 计算单元格的中心位置
            x = j + 0.5  # 水平中心
            y = len(cal) - i - 0.5  # 垂直中心

            # 获取打卡次数
            date_str = f"{year}-{month:02}-{day:02}"
            count = checkin_counts.get(date_str, 0)

            if count == 0:
                # 未打卡：显示日期
                ax.text(x, y, str(day), ha='center', va='center', fontsize=30)
            else:
                # 有打卡：插入图片
                imagebox = OffsetImage(deer_image, zoom=0.115)  # 图片大小与格子一致
                ab = AnnotationBbox(imagebox, (x, y), frameon=False)
                ax.add_artist(ab)

                if count > 1:
                    # 多次打卡：在图片上叠加红色加粗文字
                    ax.text(x, y, f"X{count}", ha='center', va='center',
                            fontsize=30, color='red', fontweight='bold')

    # 设置表格边框
    for i in range(len(cal) + 1):
        ax.axhline(i, color='black', lw=1)
    for j in range(8):
        ax.axvline(j, color='black', lw=1)

    # 设置表格范围
    ax.set_xlim(0, 7)
    ax.set_ylim(0, len(cal))

    # 保存图表到文件
    image_path = os.path.join(IMAGES_DIR, f'checkin_table_{
                              user_id}_{group_id}.png')
    plt.savefig(image_path, bbox_inches='tight', dpi=300)  # 提高分辨率
    plt.close()

    # 返回图像文件路径
    return image_path


def get_leaderboard(group_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 查询当前群组的所有用户的打卡次数，按打卡次数从高到低排序
    c.execute('''
        SELECT user_id, COUNT(*) as checkin_count
        FROM checkins
        WHERE group_id = ?
        GROUP BY user_id
        ORDER BY checkin_count DESC
    ''', (group_id,))

    # 获取查询结果
    leaderboard = c.fetchall()
    conn.close()

    return leaderboard


def clear_old_checkins():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    last_month = (datetime.now().replace(day=1) -
                  timedelta(days=1)).strftime('%Y-%m-%d')
    c.execute("DELETE FROM checkins WHERE checkin_date < ?", (last_month,))
    conn.commit()
    conn.close()


def get_qq_nick(qq_code):
    url = f'https://users.qzone.qq.com/fcg-bin/cgi_get_portrait.fcg?uins={
        qq_code}'
    headers = {'Content-Type': 'multipart/form-data;'}

    data = ' '

    response = requests.get(url, headers=headers, data=data)
    # response = requests.get(url)

    # Decode the response content to EUC-CN
    decoded_response = response.content.decode('EUC-CN')

    # Extract the JSON part from the response
    json_data = decoded_response[17:-1]
    parsed_data = json.loads(json_data)

    # Return the QQ nickname
    return parsed_data[qq_code][6]


init_db()


@register(name="Checkin", description="撸管记录", version="0.1", author="GryllsGYS")
class MyPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        pass

    async def initialize(self):
        pass

    @handler(GroupMessageReceived)
    async def group_normal_received(self, ctx: EventContext):
        msg = ctx.event.message_chain
        msg = str(msg)
        if msg == "撸" or msg == "🦌":
            clear_old_checkins()
            if checkin(ctx.event.sender_id, ctx.event.launcher_id):
                img_path = graph(ctx.event.sender_id, ctx.event.launcher_id)
                await ctx.send_message("group", ctx.event.launcher_id, [Image(path=img_path)])
                os.remove(img_path)
                await ctx.send_message("group", ctx.event.launcher_id, [At(ctx.event.sender_id), Plain("成功撸了")])

        if msg == "撸榜" or msg == "🦌榜":
            leaderboard = get_leaderboard(ctx.event.launcher_id)
            updated_leaderboard = []

            for entry in leaderboard:
                user_id = entry[0]  # 使用索引访问元组
                checkin_count = entry[1]  # 使用索引访问元组

                # 使用 get_qq_nick 函数获取用户名
                username = get_qq_nick(user_id)

                # 更新 entry 为字典
                updated_entry = {"user_id": username,
                                 "checkin_count": checkin_count}
                updated_leaderboard.append(updated_entry)

            if updated_leaderboard:
                text = "本群本月的撸管排行榜：\n"
                for i, entry in enumerate(updated_leaderboard[:10]):
                    rank = i + 1
                    if rank == 1:
                        prefix = "🥇"
                    elif rank == 2:
                        prefix = "🥈"
                    elif rank == 3:
                        prefix = "🥉"
                    else:
                        prefix = f"第{rank}名"
                    text += f"{prefix} {entry['user_id']
                                        } {entry['checkin_count']}次\n"
                text += f"{updated_leaderboard[0]['user_id']}是本群的撸管大王"

            else:
                text = "这个月还没有人撸过管哦"
            # 发送消息
            await ctx.send_message("group", ctx.event.launcher_id, [Plain(text)])
