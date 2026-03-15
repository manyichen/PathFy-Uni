import os
import json
import time
import pandas as pd
from google import genai
from py2neo import Graph, Node, Relationship
from pydantic import ValidationError

# 1. 环境配置
client = genai.Client()
graph = Graph("bolt://localhost:7687", auth=("neo4j", "testawa1234"))

# 2. 定义分析函数 (使用新版 Client 语法)
import json
import time
import sys
from google import genai
from pydantic import ValidationError

def analyze_demand_with_gemini(demand_text, max_retries=5):
    """
    分析招聘需求，带有重试机制（最多5次）
    """
    prompt = f"""
    你是一个专业的IT技术猎头和数据分析师。请分析以下[招聘需求文本]，提取关键的结构化信息。
    
    输出规范：
    - school_level: 必须是以下之一: "985/211", "一本", "本科", "大专", "硕士", "博士", "不限"。
    - certs: 仅提取行业相关的专业证书（如 ITIL, PMP, CISP, 软考, AWS认证等）。
    - soft_skills: 提取职业素养（如 沟通能力, 解决问题, 逻辑分析, 抗压等）。
    - hidden_tech: 扫描文本，提取可能被主技能列表遗漏的技术栈或工具（如 Redis, Kafka, 微服务, 网络协议等）。

    要求：
    - 严格输出 JSON 格式。
    - 如果某项未提及，该字段设为 null 或空列表 []。

    [招聘需求文本]:
    {demand_text}
    """

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview", 
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.1,
                }
            )
            
            return json.loads(response.text)

        except Exception as e:
            # 防止太频繁
            wait_seconds = attempt * 5
            print(f"第 {attempt} 次调用失败: {e}")
            
            if attempt < max_retries:
                print(f"等待 {wait_seconds} 秒后重试...")
                time.sleep(wait_seconds)
            else:
                print("连续 5 次调用失败，程序退出。")
                sys.exit(1)

    return None

def create_graph(csv_path):
    df = pd.read_csv(csv_path).fillna('')
    
    print("开始清洗旧数据并导入新数据...")
    # graph.delete_all()

    for index, row in df[100:].iterrows():
        # Job
        job = Node("Job", 
                   title=row['name'], 
                   salary=row['salary'], 
                   experience=row['experience'])
        graph.create(job)

        # Company
        company = Node("Company", name=row['company'])
        graph.merge(company, "Company", "name")
        graph.merge(Relationship(company, "PUBLISH", job))

        # 调用 gemini 分析文本
        print(f"[{index+1}/{len(df)}] 正在分析: {row['name']} @ {row['company']}")
        ai_data = analyze_demand_with_gemini(row['demand'])

        if ai_data:
            # 处理提取出的院校要求
            if ai_data.get('school_level'):
                edu_node = Node("EducationConstraint", level=ai_data['school_level'])
                graph.merge(edu_node, "EducationConstraint", "level")
                graph.merge(Relationship(job, "REQUIRES_EDU_LEVEL", edu_node))

            # 处理提取出的证书
            for cert_name in ai_data.get('certs', []):
                cert_node = Node("Certificate", name=cert_name)
                graph.merge(cert_node, "Certificate", "name")
                graph.merge(Relationship(job, "REQUIRES_CERT", cert_node))
            
            # 处理软素质
            for soft in ai_data.get('soft_skills', []):
                soft_node = Node("SoftSkill", name=soft)
                graph.merge(soft_node, "SoftSkill", "name")
                graph.merge(Relationship(job, "REQUIRES_SOFT_SKILL", soft_node))

        # skills 字段
        for s_name in row['skills'].split():
            skill_node = Node("Skill", name=s_name)
            graph.merge(skill_node, "Skill", "name")
            graph.merge(Relationship(job, "REQUIRES_TECH", skill_node))

    print("图谱构建完成！")

# 4. 运行
if __name__ == "__main__":
    create_graph("../datasets/jobs.csv")