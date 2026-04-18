from flask import Blueprint, request, jsonify, current_app
import os
import json
import pymysql

from app.config import Config
from app.utils import ocr_image, pdf_to_image, score_resume, create_radar_chart

portrait_bp = Blueprint('profile', __name__, url_prefix='/api/profile')


def get_db():
    """自己实现数据库连接，不依赖项目db.py，零冲突"""
    return pymysql.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor
    )

@portrait_bp.route('/upload', methods=['POST'])
def upload_resume():
    try:
        user_id = request.form.get('user_id')
        name = request.form.get('name')
        major = request.form.get('major')
        file = request.files.get('resume')

        if not all([user_id, name, major, file]):
            return jsonify({"code": 400, "msg": "参数不全"}), 400

        upload_dir = os.path.join(current_app.static_folder, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)
        file.save(file_path)

        if file.filename.lower().endswith('.pdf'):
            ocr_path = pdf_to_image(file_path)
        else:
            ocr_path = file_path

        resume_text = ocr_image(ocr_path)
        scores = score_resume(resume_text)
        radar_html = create_radar_chart(scores)

        conn = get_db()
        cur = conn.cursor()
        sql = """
        INSERT INTO student_resume
        (user_id, name, major, resume_text,
        cap_req_theory, cap_req_cross, cap_req_practice, cap_req_digital,
        cap_req_innovation, cap_req_teamwork, cap_req_social, cap_req_growth,
        completeness, competitiveness, radar_html)
        VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s)
        """
        total = sum(scores.values())
        completeness = total // 8
        competitiveness = total // 8
        cur.execute(sql, (
            user_id, name, major, resume_text,
            scores["cap_req_theory"], scores["cap_req_cross"],
            scores["cap_req_practice"], scores["cap_req_digital"],
            scores["cap_req_innovation"], scores["cap_req_teamwork"],
            scores["cap_req_social"], scores["cap_req_growth"],
            completeness, competitiveness, radar_html
        ))
        conn.commit()
        resume_id = cur.lastrowid
        conn.close()

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "resume_id": resume_id,
                "scores": scores,
                "completeness": completeness,
                "competitiveness": competitiveness
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500

@portrait_bp.route('/result/<int:resume_id>', methods=['GET'])
def get_result(resume_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM student_resume WHERE id = %s", (resume_id,))
        result = cur.fetchone()
        conn.close()
        if not result:
            return jsonify({"code": 404, "msg": "结果不存在"}), 404
        return jsonify({"code": 200, "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"错误: {str(e)}"}), 500