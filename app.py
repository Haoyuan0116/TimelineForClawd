from flask import Flask, render_template, request, jsonify
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from config import MINIMAX_API_KEY

app = Flask(__name__)

# MiniMax API 配置
OPENAI_BASE_URL = "https://api.minimaxi.com/v1"

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=MINIMAX_API_KEY,
    base_url=OPENAI_BASE_URL
)

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
BASE_DIR = os.path.dirname(__file__)


def ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_json(filepath, default=None):
    """加载JSON文件"""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default


def save_json(filepath, data):
    """保存JSON文件"""
    ensure_data_dir()
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_timeline(date_str):
    """加载指定日期的时间轴数据"""
    timeline_file = os.path.join(DATA_DIR, f'timeline_{date_str}.json')

    if not os.path.exists(timeline_file):
        return None

    with open(timeline_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def merge_timeline():
    """合并三个来源的数据成时间轴"""
    sources = [
        ('chrome', os.path.join(BASE_DIR, 'after_data', 'after_chrome.json')),
        ('claude_code', os.path.join(BASE_DIR, 'after_data', 'after_claudecode.json')),
        ('phone_ocr', os.path.join(BASE_DIR, 'after_data', 'after_phoneocr.json'))
    ]

    all_records = []

    for source_name, file_path in sources:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
                for record in records:
                    record['source_type'] = source_name
                all_records.extend(records)

    # 按时间排序
    all_records.sort(key=lambda x: x.get('time', ''))

    return all_records


def decompose_task_with_ai(task_name, task_description):
    """调用 MiniMax API 将任务拆解为子任务"""
    if not task_name:
        return []

    print(f"步骤1 - 开始调用API，任务名称: {task_name}")

    # 构建提示词
    prompt = f"""请将以下任务拆解为3-5个子任务。返回JSON数组格式，每个子任务只需包含name字段。

任务名称: {task_name}
任务描述: {task_description}

请直接返回JSON数组，不要其他内容。格式例如：
[{{"name": "子任务1名称"}}, {{"name": "子任务2名称"}}, {{"name": "子任务3名称"}}]"""

    try:
        print(f"步骤2 - 发送API请求...")
        response = client.chat.completions.create(
            model="MiniMax-M2.5",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        print(f"步骤3 - API返回结果:")
        print(f"完整响应: {response}")
        print(f"响应类型: {type(response)}")
        
        # 检查响应是否有choices属性
        if hasattr(response, 'choices'):
            print(f"步骤4 - response有choices属性")
            print(f"choices: {response.choices}")
            print(f"choices类型: {type(response.choices)}")
            
            if response.choices:
                print(f"步骤5 - choices不为空")
                first_choice = response.choices[0]
                print(f"第一个choice: {first_choice}")
                print(f"choice类型: {type(first_choice)}")
                
                if hasattr(first_choice, 'message'):
                    print(f"步骤6 - choice有message属性")
                    message = first_choice.message
                    print(f"message: {message}")
                    print(f"message类型: {type(message)}")
                    
                    if hasattr(message, 'content'):
                        print(f"步骤7 - message有content属性")
                        content = message.content
                        print(f"content: {content}")
                        print(f"content类型: {type(content)}")
                        print(f"content长度: {len(content) if content else 0}")
                        
                        if content:
                            print(f"步骤8 - 开始解析content内容")
                            print(f"原始content: '{content}'")
                            
                            # 从content中提取JSON数组（可能包含thinking内容，需要提取[...]部分）
                            import re
                            print(f"步骤9 - 尝试用正则表达式提取JSON数组...")

                            # 先去掉think标签内容和JSON数组之前的所有内容
                            # 去掉 <think> 和 </think> 标签
                            content_clean = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

                            # 从清理后的内容中提取JSON数组
                            # 匹配 [...] 格式的JSON数组
                            match = re.search(r'\[.*?\]', content_clean, re.DOTALL)
                            if match:
                                print(f"步骤10 - 正则匹配成功")
                                json_str = match.group(0)
                                print(f"提取的JSON字符串: '{json_str}'")

                                try:
                                    sub_tasks = json.loads(json_str)
                                    print(f"步骤11 - JSON解析成功")
                                    print(f"解析结果: {sub_tasks}")
                                    print(f"结果类型: {type(sub_tasks)}")

                                    if isinstance(sub_tasks, list):
                                        print(f"步骤12 - 成功返回子任务列表")
                                        return sub_tasks
                                    else:
                                        print(f"步骤12A - 解析结果不是列表")
                                except Exception as e:
                                    print(f"步骤11A - JSON解析失败: {e}")
                                
                                print(f"步骤12B - 正则解析失败，尝试直接解析content...")
                                try:
                                    sub_tasks = json.loads(content)
                                    print(f"步骤13 - 直接解析成功")
                                    print(f"解析结果: {sub_tasks}")
                                    return sub_tasks if isinstance(sub_tasks, list) else []
                                except Exception as e:
                                    print(f"步骤13A - 直接解析也失败: {e}")
                                    print(f"步骤14 - 返回默认子任务")
                                    return [{"name": "完成主要任务"}]
                            else:
                                print(f"步骤10A - 正则匹配失败，尝试直接解析...")
                                try:
                                    sub_tasks = json.loads(content)
                                    print(f"步骤15 - 直接解析成功")
                                    return sub_tasks if isinstance(sub_tasks, list) else []
                                except Exception as e:
                                    print(f"步骤15A - 直接解析失败: {e}")
                                    return [{"name": "完成主要任务"}]
                        else:
                            print(f"步骤8A - content为空")
                            return [{"name": "完成主要任务"}]
                    else:
                        print(f"步骤7A - message没有content属性")
                        return [{"name": "完成主要任务"}]
                else:
                    print(f"步骤6A - choice没有message属性")
                    return [{"name": "完成主要任务"}]
            else:
                print(f"步骤5A - choices为空")
                return [{"name": "完成主要任务"}]
        else:
            print(f"步骤4A - response没有choices属性")
            return [{"name": "完成主要任务"}]

    except Exception as e:
        print(f"AI拆解任务失败: {e}")
        import traceback
        traceback.print_exc()
        return [{"name": "完成主要任务"}]


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页 - 时间轴"""
    return render_template('index.html')


@app.route('/tasks')
def tasks():
    """任务仪表盘"""
    return render_template('task_dashboard.html')


@app.route('/input')
def task_input():
    """任务输入页面"""
    return render_template('task_input.html')


@app.route('/analysis')
def analysis():
    """AI分析页面"""
    return render_template('analysis.html')


@app.route('/night-tasks')
def night_tasks():
    """夜间任务页面"""
    return render_template('night_tasks.html')


# ==================== API接口 ====================

@app.route('/api/timeline/<date_str>')
def get_timeline(date_str):
    """获取指定日期的时间轴数据"""
    date_str = date_str.replace('.', '-')

    timeline = load_timeline(date_str)

    if timeline is None:
        timeline = merge_timeline()

        data_file = os.path.join(DATA_DIR, f'timeline_{date_str}.json')
        save_json(data_file, timeline)

    timeline.sort(key=lambda x: x.get('time', ''))

    return jsonify({
        'date': date_str,
        'count': len(timeline),
        'timeline': timeline
    })


@app.route('/api/sources')
def get_sources():
    """获取可用数据源统计"""
    sources = {
        'chrome': os.path.join(BASE_DIR, 'after_data', 'after_chrome.json'),
        'claude_code': os.path.join(BASE_DIR, 'after_data', 'after_claudecode.json'),
        'phone_ocr': os.path.join(BASE_DIR, 'after_data', 'after_phoneocr.json')
    }

    result = {}
    for name, path in sources.items():
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                result[name] = len(data)

    return jsonify(result)


@app.route('/api/tasks', methods=['GET', 'POST'])
def manage_tasks():
    """获取或保存任务配置"""
    tasks_file = os.path.join(DATA_DIR, 'user_tasks.json')

    if request.method == 'GET':
        tasks = load_json(tasks_file, {
            'tasks': [],
            'created_at': '',
            'updated_at': ''
        })
        return jsonify(tasks)

    # POST - 保存任务
    data = request.get_json()

    # 处理任务（含子任务）
    task_list = data.get('tasks', [])
    processed_tasks = []
    for task in task_list:
        sub_tasks = task.get('sub_tasks', [])

        # 根据子任务状态自动计算父任务状态
        # 只要有一个子任务未完成，父任务即为pending；全部完成才为completed
        if sub_tasks:
            all_completed = all(s.get('status') == 'completed' for s in sub_tasks)
            task_status = 'completed' if all_completed else 'pending'
        else:
            task_status = task.get('status', 'pending')

        processed_task = {
            'id': task.get('id', f'task_{uuid.uuid4().hex[:8]}'),
            'name': task.get('name', ''),
            'description': task.get('description', ''),
            'status': task_status,
            'deadline': task.get('deadline'),
            'sub_tasks': [],
            'created_at': task.get('created_at', datetime.now(BEIJING_TZ).isoformat())
        }
        # 处理子任务
        for sub in sub_tasks:
            processed_task['sub_tasks'].append({
                'id': sub.get('id', f'sub_{uuid.uuid4().hex[:8]}'),
                'name': sub.get('name', ''),
                'status': sub.get('status', 'pending')
            })
        processed_tasks.append(processed_task)

    tasks_config = {
        'tasks': processed_tasks,
        'updated_at': datetime.now(BEIJING_TZ).isoformat()
    }

    # 如果没有created_at，设置为当前时间
    existing = load_json(tasks_file, {})
    if not existing.get('created_at'):
        tasks_config['created_at'] = datetime.now(BEIJING_TZ).isoformat()
    else:
        tasks_config['created_at'] = existing['created_at']

    save_json(tasks_file, tasks_config)

    return jsonify({'success': True, 'tasks': tasks_config})


@app.route('/api/decompose', methods=['POST'])
def decompose_task():
    """调用AI拆解任务为子任务"""
    data = request.get_json()
    task_name = data.get('task_name', '')
    task_description = data.get('task_description', '')

    if not task_name:
        return jsonify({'success': False, 'error': '任务名称不能为空'})

    # 调用AI拆解
    sub_tasks = decompose_task_with_ai(task_name, task_description)

    # 为每个子任务生成ID和默认状态
    result = []
    for i, sub in enumerate(sub_tasks):
        result.append({
            'id': f'sub_{uuid.uuid4().hex[:8]}_{i}',
            'name': sub.get('name', ''),
            'status': 'pending'
        })

    return jsonify({
        'success': True,
        'sub_tasks': result
    })


@app.route('/api/task-behaviors', methods=['GET'])
def get_task_behaviors():
    """获取任务行为归类结果"""
    behaviors_file = os.path.join(DATA_DIR, 'task_behaviors.json')
    return jsonify(load_json(behaviors_file, {}))


@app.route('/api/analyze', methods=['POST'])
def run_analysis():
    """运行AI分析"""
    # 加载用户任务
    tasks_file = os.path.join(DATA_DIR, 'user_tasks.json')
    tasks = load_json(tasks_file, {'tasks': [], 'created_at': '', 'updated_at': ''})

    # 加载时间轴数据
    timeline = merge_timeline()

    # 简单的规则匹配分析（实际项目中可以调用LLM API）
    task_analysis = []
    all_tasks = tasks.get('tasks', [])

    for task in all_tasks:
        # 统计匹配的行为（这里用简单的关键词匹配演示）
        task_keywords = task.get('name', '').split() + task.get('description', '').split()
        matched = []

        for record in timeline:
            content = json.dumps(record, ensure_ascii=False)
            for keyword in task_keywords:
                if keyword and keyword in content:
                    matched.append(record)
                    break

        analysis_result = {
            'task_id': task.get('id'),
            'task_name': task.get('name'),
            'matched_count': len(matched),
            'progress': min(len(matched) * 5, 100),  # 简单估算进度
            'analysis': f'根据{task.get("name")}的关键词，分析到{len(matched)}条相关行为记录'
        }
        task_analysis.append(analysis_result)

    # 生成夜间建议
    night_suggestions = []
    for task in all_tasks:
        if task.get('status') != 'completed':
            suggestion = {
                'task_id': task.get('id'),
                'description': f'搜索关于"{task.get("name")}"的相关资料和进展',
                'related_task': task.get('name'),
                'suggested_time': '22:00'
            }
            night_suggestions.append(suggestion)

    # 保存分析结果
    behaviors_file = os.path.join(DATA_DIR, 'task_behaviors.json')
    behaviors_data = {t['task_id']: {'matched_records': [], 'progress_percent': min(t['matched_count'] * 5, 100)}
                      for t in task_analysis}
    save_json(behaviors_file, behaviors_data)

    # 保存夜间任务建议
    night_tasks_file = os.path.join(DATA_DIR, 'night_tasks.json')
    night_data = {
        'date': datetime.now(BEIJING_TZ).strftime('%Y-%m-%d'),
        'tasks': [{'id': f'night_{i}', **s, 'confirmed': False, 'executed': False}
                  for i, s in enumerate(night_suggestions)]
    }
    save_json(night_tasks_file, night_data)

    return jsonify({
        'success': True,
        'task_analysis': task_analysis,
        'night_suggestions': night_suggestions
    })


@app.route('/api/night-tasks', methods=['GET'])
def get_night_tasks():
    """获取夜间任务"""
    night_file = os.path.join(DATA_DIR, 'night_tasks.json')
    return jsonify(load_json(night_file, {'date': '', 'tasks': []}))


@app.route('/api/night-tasks/<task_id>/confirm', methods=['POST'])
def confirm_night_task(task_id):
    """确认夜间任务"""
    night_file = os.path.join(DATA_DIR, 'night_tasks.json')
    night_data = load_json(night_file, {'date': '', 'tasks': []})

    for task in night_data.get('tasks', []):
        if task.get('id') == task_id:
            task['confirmed'] = True

    save_json(night_file, night_data)

    return jsonify({'success': True})


if __name__ == '__main__':
    print("=" * 50)
    print("TimelineForClawd Flask App")
    print("=" * 50)
    print("访问地址: http://127.0.0.1:5000")
    print("页面列表:")
    print("  /          - 时间轴")
    print("  /tasks     - 任务仪表盘")
    print("  /input     - 任务输入")
    print("  /analysis  - AI分析")
    print("  /night-tasks - 夜间任务")
    print("=" * 50)

    app.run(debug=True, host='127.0.0.1', port=5000)