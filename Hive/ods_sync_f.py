# -*- coding: utf-8 -*-
import Queue
import argparse
import json
import os
import random
import re
import subprocess
import threading
import urllib2
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import logging

# 配置日志记录器
log_filename = os.path.join('/home/big-data-sync/ods_sync/log', datetime.now().strftime('ods_sync_f_%Y%m%d_%H%M%S.log'))
logging.basicConfig(
    filename=log_filename,  # 指定日志输出文件
    level=logging.INFO,  # 设置日志记录级别为 INFO
    format='%(asctime)s - %(levelname)s - %(message)s'  # 设置日志格式
)

# 发送消息到企业微信机器人
def send_to_wechat(message,WECHAT_WEBHOOK_URL):
    """
        发送消息到企业微信机器人
        :param webhook_url: 机器人的 webhook 地址
        :param message: 发送的消息内容，必须是 JSON 格式
        """
    headers = {
        'Content-Type': 'application/json',
    }

    data = {
        "msgtype": "text",  # 消息类型
        "text": {
            "content": message  # 你想发送的消息内容
        }
    }

    # 将数据转为 JSON 格式
    json_data = json.dumps(data).encode('utf-8')

    try:
        # 使用 urllib2 发送 POST 请求
        req = urllib2.Request(WECHAT_WEBHOOK_URL, json_data, headers)
        response = urllib2.urlopen(req)
        # 获取返回内容
        result = response.read().decode('utf-8')  # 确保解码为字符串
        logging.info("消息发送成功: {}".format(result))
    except urllib2.URLError as e:
        logging.error("消息发送失败: {}".format(e))

def execute_beeline_command(command):
    """
    使用 Beeline 执行命令。
    :param command: 要执行的 SQL 或命令
    """
    try:
        # 构造 Beeline 命令
        beeline_cmd = "$CLIENT_HIVE_URL"
        beeline_cmd += " --outputformat=tsv2 -e \'{}\'".format(command)

        # 执行命令
        result = subprocess.Popen(
            beeline_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = result.communicate()
        # 如果你需要将字节流解码为字符串
        stdout = stdout.decode('utf-8')  # 对于 Python 2，确保使用正确的解码方式
        lines = stdout.splitlines()

        if result.returncode == 0:
            return len(lines)
        else:
            return None
    except Exception as e:
        logging.error("发生错误: {}".format(e))

def execute_beeline_command_application_id(command):
    """
        使用 Beeline 执行 SQL 命令，并判断执行结果，若失败则返回 application_id。
        :param command: 要执行的 SQL 或命令
        :return: (success, application_id) 其中 success 是布尔值，表示执行是否成功，
                如果失败，application_id 是错误信息中的 ID。
        """
    global stderr
    try:
        # 构造 Beeline 命令
        beeline_cmd = "$CLIENT_HIVE_URL"  # Beeline 客户端的 URL
        beeline_cmd += " --outputformat=tsv2 -e \"{}\"".format(command)

        # 执行命令
        result = subprocess.Popen(
            beeline_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = result.communicate()

        # 将输出和错误信息解码为字符串
        stdout = stdout.decode('utf-8')
        stderr = stderr.decode('utf-8')

        if result.returncode == 0:
            # 执行成功
            return True, None
        else:
            # 执行失败，尝试从错误输出中提取 application_id
            application_id = None
            # 正则表达式查找可能的 application_id
            match = re.search(r"application_[0-9]+_[0-9]+", stderr)
            if match:
                application_id = match.group(0)
            return False, application_id

    except Exception as e:
        logging.error("执行过程中发生错误: {}".format(e))
        # 执行失败，尝试从错误输出中提取 application_id
        application_id = None
        # 正则表达式查找可能的 application_id
        match = re.search(r"application_[0-9]+_[0-9]+", stderr)
        if match:
            application_id = match.group(0)
        return False, application_id[0]

def migrate_data(src_db, dest_db, table_name, incremental_date=None):
    """
    将数据从源库迁移到目标库。如果目标表已存在，使用 INSERT OVERWRITE 覆盖数据。
    :param src_db: 源库名
    :param dest_db: 目标库名
    :param table_name: 表名
    :param incremental_date: 增量同步时间点 (yyyy-MM-dd)
    """
    # 构造增量同步过滤条件
    where_clause = "WHERE etl_date = \"{}\"".format(incremental_date) if incremental_date else ""

    # 检查目标表是否存在
    check_table_sql = """SHOW TABLES IN {} LIKE "{}";""".format(dest_db, table_name)
    result = execute_beeline_command(check_table_sql)
    # 当返回行数是2时，表示库中已经存在此表
    if result > 1:
        logging.info("目标表 {}.{} 已存在，使用 INSERT OVERWRITE 覆盖数据。".format(dest_db, table_name))
        # 使用 INSERT OVERWRITE 覆盖目标表数据
        migration_sql = """
                set hive.exec.dynamic.partition = true;set hive.exec.dynamic.partition.mode = nonstrict;set hive.exec.max.dynamic.partitions.pernode = 4000;set hive.exec.max.dynamic.partitions = 4000;
                INSERT OVERWRITE TABLE {}.{} SELECT * FROM {}.{} ;
            """.format(dest_db, table_name, src_db, table_name)
        # if where_clause and 'i' in table_name:
        #     migration_sql = migration_sql.replace(";", " {}".format(where_clause) + ";")
        result2 = execute_beeline_command_application_id(migration_sql)
        return result2
    else:
        # 表不存在时创建新表并迁移数据
        migration_sql = """
                set hive.exec.dynamic.partition = true;set hive.exec.dynamic.partition.mode = nonstrict;set hive.exec.max.dynamic.partitions.pernode = 4000;set hive.exec.max.dynamic.partitions = 4000;
                CREATE TABLE {}.{} AS
                SELECT * FROM {}.{};
            """.format(dest_db, table_name, src_db, table_name)
        result3 = execute_beeline_command_application_id(migration_sql)
        return result3

def validate_data_count(src_db, dest_db, table_name, incremental_date=None):
    """
    校验源表与目标表记录数是否一致。
    :param src_db: 源库名
    :param dest_db: 目标库名
    :param table_name: 表名
    :param incremental_date: 增量同步时间点 (yyyy-MM-dd)
    """
    where_clause = "WHERE etl_date >= '{}'".format(incremental_date) if incremental_date else ""

    # 源表记录数 SQL
    src_count_sql = "SELECT COUNT(*) FROM {}.{} {};".format(src_db, table_name, where_clause)
    src_count = int(execute_beeline_command(src_count_sql))

    # 目标表记录数 SQL
    dest_count_sql = "SELECT COUNT(*) FROM {}.{} {};".format(dest_db, table_name, where_clause)
    dest_count = int(execute_beeline_command(dest_count_sql))

    if src_count == dest_count:
        logging.info("数据校验通过：源表和目标表记录数一致 ({} 条)。".format(src_count))
    else:
        logging.info("数据校验失败：源表记录数 {} 条，目标表记录数 {} 条。".format(src_count, dest_count))

# 全局变量用于记录成功和失败的表数量
success_count = 0
failure_count = 0
failed_tables = []  # 用于记录迁移失败的表名 和 application_id

# 创建线程锁，确保对全局计数器的修改是线程安全的
lock = threading.Lock()

def batch_migrate_and_validate(src_db, dest_db, tables, incremental_date=None):
    """
    批量迁移数据并校验。
    :param src_db: 源库名
    :param dest_db: 目标库名
    :param tables: 表名列表
    :param incremental_date: 增量同步时间点 (yyyy-MM-dd)
    """
    global success_count, failure_count  # 声明使用全局变量

    # 创建线程池和线程安全队列
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []

        # 使用队列，确保每个表只有一个线程处理
        table_queue = Queue.Queue()
        for table_name in tables:
            table_queue.put(table_name)  # 将表名添加到队列中

        # 定义线程任务，逐个取出表名并迁移
        def worker():
            global success_count, failure_count
            while not table_queue.empty():
                table_name = table_queue.get()
                try:
                    # 迁移数据
                    logging.info("正在迁移表：{}".format(table_name))
                    success, application_id = migrate_data(src_db, dest_db, table_name, incremental_date)
                    # 根据返回值判断迁移是否成功
                    with lock:
                        if success:
                            success_count += 1
                            logging.info("表 {} 迁移成功".format(table_name))
                        else:
                            failure_count += 1
                            failed_tables.append({"table_name": table_name, "application_id": application_id})    # 将失败的表名添加到失败列表
                            logging.error("表 {} 迁移失败".format(table_name))

                except Exception as e:
                    # 捕获每个表的异常，确保一个表出错不会影响其他表
                    with lock:
                        failure_count += 1
                        failed_tables.append(table_name)  # 将失败的表名添加到失败列表
                    logging.error("表 {} 迁移失败，错误：{}".format(table_name, e))
                finally:
                    table_queue.task_done()  # 确保任务被标记为完成

        # 启动线程池执行任务
        for _ in range(5):  # 启动5个线程来处理
            executor.submit(worker)

        # 等待所有任务完成
        table_queue.join()  # 等待队列中所有任务完成

    # 打印最终结果和当前时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info("ods全量迁移完成：")
    logging.info("\n迁移完成时间：{}".format(current_time))
    logging.info("成功迁移的表数量：{}".format(success_count))
    logging.info("迁移失败的表数量：{}".format(failure_count))

    # 如果有失败的表，打印失败的表名
    logging.info("table_name,application_id")  # 打印标题
    logging.info("-------------------------")  # 打印标题
    for row in failed_tables:
        output = "{},{}".format(row.get("table_name"), row.get("application_id"))
        logging.info(output)


    # 企业微信机器人 webhook 地址
    WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d9608e53-abc0-407b-8e1e-09b037eefda0"
    # 构建消息内容，使用换行符来分隔各行
    message = ""
    message += "\nods全量迁移完成："
    message += "\n迁移完成时间：{}".format(current_time)
    message += "\n成功迁移的表数量：{}".format(success_count)
    message += "\n迁移失败的表数量：{}".format(failure_count)

    # 如果有失败的表，打印失败的表名
    message += "\ntable_name,application_id"  # 打印标题
    message += "\n-------------------------"  # 打印标题
    for row in failed_tables:
        output = "{},{}".format(row.get("table_name"), row.get("application_id"))
        message += "\n{}".format(output)
    # 发送消息到企业微信
    send_to_wechat(message,WECHAT_WEBHOOK_URL)

def get_tables_from_hive(command):
    """
    使用 Beeline 执行命令。
    :param command: 要执行的 SQL 或命令
    """
    try:
        # 构造 Beeline 命令
        beeline_cmd = "$CLIENT_HIVE_URL"
        beeline_cmd += " --outputformat=tsv2 -e \'{}\'".format(command)

        # 执行命令
        result = subprocess.Popen(
            beeline_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = result.communicate()
        # 如果你需要将字节流解码为字符串
        stdout = stdout.decode('utf-8')  # 对于 Python 2，确保使用正确的解码方式
        output = stdout.strip()
        ods_table = output.split("\n")
        ods_table.pop(0)

        if result.returncode == 0:
            return ods_table
        else:
            raise Exception("获取ods_prod库表失败")
    except Exception as e:
        logging.error("发生错误: {}".format(e))


def parse_args():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description="批量迁移数据")

    # tables_to_migrate 接收一个可选的表名列表
    parser.add_argument('--tables_to_migrate', nargs='*', help="要迁移的表名列表，空格分隔", default=None)

    # incremental_date 接收一个日期字符串（格式：yyyy-MM-dd）
    parser.add_argument('--incremental_date', type=str, help="增量同步的日期 (yyyy-MM-dd)", default=None)

    return parser.parse_args()  # 返回解析后的命令行参数


if __name__ == "__main__":
    # python ods_sync_i.py --tables_to_migrate ods_np_order_recharge_flow_i --incremental_date 1988-01-01
    # 解析命令行参数
    args = parse_args()

    # 配置参数
    src_database = "ods_prod"  # 源库
    dest_database = "ods_test"  # 目标库

    # 优先使用传入的 tables_to_migrate 参数，否则通过 Beeline 获取表名
    tables_to_migrate = args.tables_to_migrate if args.tables_to_migrate is not None else get_tables_from_hive('SHOW TABLES IN ods_prod;')

    # 优先使用传入的 incremental_date 参数，否则使用当前日期减去默认增量天数
    incremental_days = 1
    incremental_date = args.incremental_date if args.incremental_date is not None else (datetime.now() - timedelta(days=incremental_days)).strftime("%Y-%m-%d")

    # 执行批量迁移
    batch_migrate_and_validate(src_database, dest_database, tables_to_migrate, incremental_date)
