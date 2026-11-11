import subprocess
import os
import base64

def generate_pdf():
    # 1. Read Logo as base64 to embed directly in HTML
    logo_path = os.path.abspath('static/images/logo.png')
    logo_b64 = ""
    if os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            logo_b64 = "data:image/png;base64," + base64.b64encode(f.read()).decode('utf-8')

    html_content = f"""<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <title>ELEV8 AI Planner - API & Model Documentation</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Sarabun:ital,wght@0,300;0,400;0,600;0,700;1,400&family=Fira+Code:wght@400;600&display=swap" rel="stylesheet">
    <style>
        @page {{
            size: A4;
            margin: 20mm 15mm 20mm 15mm;
            @bottom-right {{
                content: counter(page);
                font-family: 'Sarabun', sans-serif;
                font-size: 9pt;
                color: #64748b;
            }}
        }}

        * {{
            box-sizing: border-box;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}

        body {{
            font-family: 'Sarabun', sans-serif;
            font-size: 10.5pt;
            line-height: 1.6;
            color: #1e293b;
            margin: 0;
            padding: 0;
            background-color: #ffffff;
        }}

        .page-break {{
            page-break-before: always;
        }}

        .no-break {{
            page-break-inside: avoid;
        }}

        /* Header & Cover Banner */
        .cover-header {{
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            color: white;
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 15px rgba(2, 132, 199, 0.2);
        }}

        .cover-title {{
            margin: 0;
            font-size: 24pt;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}

        .cover-subtitle {{
            margin: 6px 0 0 0;
            font-size: 12pt;
            color: #e0f2fe;
            font-weight: 400;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 8.5pt;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-yellow {{
            background-color: #fef3c7;
            color: #92400e;
            border: 1px solid #fde68a;
        }}

        .badge-blue {{
            background-color: #e0f2fe;
            color: #0369a1;
            border: 1px solid #bae6fd;
        }}

        .badge-green {{
            background-color: #dcfce7;
            color: #166534;
            border: 1px solid #bbf7d0;
        }}

        h2 {{
            color: #0f172a;
            font-size: 15pt;
            font-weight: 700;
            margin-top: 25px;
            margin-bottom: 12px;
            padding-bottom: 6px;
            border-bottom: 2px solid #e2e8f0;
            display: flex;
            align-items: center;
        }}

        h2 .section-num {{
            background-color: #0284c7;
            color: white;
            width: 26px;
            height: 26px;
            border-radius: 8px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 10pt;
            margin-right: 10px;
        }}

        h3 {{
            color: #0369a1;
            font-size: 12pt;
            font-weight: 600;
            margin-top: 18px;
            margin-bottom: 8px;
        }}

        p {{
            margin: 0 0 10px 0;
        }}

        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0 18px 0;
            font-size: 9.5pt;
        }}

        th {{
            background-color: #f8fafc;
            color: #334155;
            font-weight: 700;
            text-align: left;
            padding: 8px 10px;
            border: 1px solid #cbd5e1;
        }}

        td {{
            padding: 8px 10px;
            border: 1px solid #e2e8f0;
            vertical-align: top;
        }}

        tr:nth-child(even) {{
            background-color: #f8fafc;
        }}

        /* Code & Pre Blocks */
        code {{
            font-family: 'Fira Code', monospace;
            font-size: 8.5pt;
            background-color: #f1f5f9;
            color: #0f172a;
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid #e2e8f0;
        }}

        pre {{
            font-family: 'Fira Code', monospace;
            font-size: 8pt;
            background-color: #0f172a;
            color: #f8fafc;
            padding: 12px;
            border-radius: 10px;
            overflow-x: auto;
            margin: 10px 0 16px 0;
            line-height: 1.45;
            border: 1px solid #334155;
        }}

        .info-card {{
            background-color: #f8fafc;
            border-left: 4px solid #0284c7;
            padding: 12px 16px;
            border-radius: 0 10px 10px 0;
            margin: 14px 0;
            font-size: 9.5pt;
        }}

        .highlight-card {{
            background-color: #fffbeb;
            border-left: 4px solid #f59e0b;
            padding: 12px 16px;
            border-radius: 0 10px 10px 0;
            margin: 14px 0;
            font-size: 9.5pt;
        }}

        .footer-note {{
            margin-top: 30px;
            text-align: center;
            font-size: 8.5pt;
            color: #94a3b8;
            border-top: 1px solid #e2e8f0;
            padding-top: 10px;
        }}
    </style>
</head>
<body>

    <!-- Cover Header Banner -->
    <div class="cover-header">
        <div>
            <span class="badge badge-yellow" style="margin-bottom: 8px;">TECHNICAL DOCUMENTATION</span>
            <h1 class="cover-title">ELEV8 AI Planner</h1>
            <p class="cover-subtitle">เอกสารระบุข้อมูล API ทั้งหมด, สเปก Model AI และคำอธิบายผลลัพธ์ของระบบ</p>
        </div>
        <div>
            {'<img src="' + logo_b64 + '" style="width: 75px; height: 75px; background: white; border-radius: 16px; padding: 4px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">' if logo_b64 else ''}
        </div>
    </div>

    <div class="info-card">
        <strong>ภาพรวมสถาปัตยกรรม (System Overview):</strong> ระบบ ELEV8 AI Planner ทำงานในรูปแบบ <strong>Cloud-Integrated Hybrid Architecture</strong> เชื่อมต่อ Google Classroom เพื่อดึงการบ้านของนักศึกษา ส่งเข้าประมวลผลผ่าน n8n Workflow Automation และ AI Chat Completion API เพื่อวิเคราะห์แตกงานย่อยเป็นภาษาไทย จากนั้นซิงค์ข้อมูลลง Google Sheets โดยตรงแบบไม่ต้องพึ่งพา Local MySQL/XAMPP
    </div>

    <!-- Section 1 -->
    <h2><span class="section-num">1</span> รายชื่อ API ทั้งหมดที่ใช้งานในระบบ (API Directory)</h2>
    <p>ระบบมีการเชื่อมต่อและใช้งาน API หลักทั้งหมด <strong>5 บริการภายนอก</strong> ควบคู่กับ <strong>REST API ภายในระบบ</strong> ดังนี้:</p>

    <table>
        <thead>
            <tr>
                <th style="width: 25%;">ชื่อ API</th>
                <th style="width: 20%;">ผู้ให้บริการ / ชนิด</th>
                <th style="width: 25%;">Endpoints หลัก</th>
                <th style="width: 30%;">หน้าที่และความรับผิดชอบ</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Google Classroom API (v1)</strong></td>
                <td>Google Workspace (OAuth 2.0)</td>
                <td>
                    <code>/v1/courses</code><br>
                    <code>/v1/courses/{{id}}/courseWork</code>
                </td>
                <td>ดึงรายชื่อวิชาที่กำลังเรียน (Enrolled Courses) และรายการการบ้านพร้อมกำหนดส่งของนักศึกษา</td>
            </tr>
            <tr>
                <td><strong>Google Sheets API (v4)</strong></td>
                <td>Google Workspace (OAuth 2.0)</td>
                <td>
                    <code>/v4/spreadsheets/{{id}}/values</code><br>
                    (GET, UPDATE, APPEND, CLEAR)
                </td>
                <td>ทำหน้าที่เป็น Cloud Database กลาง จัดเก็บ Assignments, Subtasks และ Execution Logs แบบ Realtime</td>
            </tr>
            <tr>
                <td><strong>OpenAI Chat Completions API</strong></td>
                <td>OpenAI (API Key Auth)</td>
                <td><code>/v1/chat/completions</code></td>
                <td>โมเดลสมองกลหลัก (AI Engine) สำหรับย่อยงานการบ้านออกเป็น Subtasks พร้อมกำหนดความสำคัญและเวลา</td>
            </tr>
            <tr>
                <td><strong>n8n Webhook API</strong></td>
                <td>Automation Orchestrator (HTTP POST)</td>
                <td>
                    <code>/webhook/project-planner</code><br>
                    <code>/webhook-test/project-planner</code>
                </td>
                <td>เป็น Workflow Pipeline จัดการรับ Request, รัน AI, ตรวจสอบ Validation Loop, ซิงค์ลง Sheet และส่งเมล</td>
            </tr>
            <tr>
                <td><strong>Gmail SMTP Notification API</strong></td>
                <td>Google SMTP Server</td>
                <td><code>smtp.gmail.com:587</code></td>
                <td>ส่งสรุปโครงสร้าง Blueprint ของการบ้านและงานย่อยแจ้งเตือนไปยังอีเมลนักศึกษา</td>
            </tr>
            <tr>
                <td><strong>Internal Web REST API</strong></td>
                <td>Flask Framework (Python)</td>
                <td>
                    <code>/api/classroom/fetch</code><br>
                    <code>/api/plan/validate-and-generate</code><br>
                    <code>/api/subtasks/{{id}}/status</code><br>
                    <code>/api/clear-data</code>
                </td>
                <td>ให้บริการ Frontend รับส่งคำสั่งจาก Dashboard และจัดการอัปเดตสถานะงานแบบ Real-time Optimistic UI</td>
            </tr>
        </tbody>
    </table>

    <div class="page-break"></div>

    <!-- Section 2 -->
    <h2><span class="section-num">2</span> ข้อมูลจำเพาะของ Model AI ที่ใช้ (AI Models Specification)</h2>
    <p>ระบบกำหนดโมเดลปัญญาประดิษฐ์สำหรับการวางแผนงานวิชาการ (Academic Project Planning) อย่างชัดเจนดังนี้:</p>

    <div class="no-break">
        <h3>2.1 โมเดลหลัก (Primary LLM Engine): OpenAI gpt-4o-mini</h3>
        <table>
            <tr>
                <th style="width: 30%;">พารามิเตอร์</th>
                <th style="width: 70%;">การกำหนดค่า (Configuration) และเหตุผล</th>
            </tr>
            <tr>
                <td><strong>Model Identifier</strong></td>
                <td><code>gpt-4o-mini</code></td>
            </tr>
            <tr>
                <td><strong>ผู้พัฒนา</strong></td>
                <td>OpenAI</td>
            </tr>
            <tr>
                <td><strong>Temperature</strong></td>
                <td><code>0.2</code> (ค่าต่ำเพื่อลดความเพ้อฝัน และเน้นผลลัพธ์ที่เป็นขั้นตอนตามหลักเกณฑ์วิชาการ)</td>
            </tr>
            <tr>
                <td><strong>Response Format</strong></td>
                <td><code>{{"type": "json_object"}}</code> (บังคับโครงสร้างเอาต์พุตให้อยู่ในรูป JSON ที่ถูกต้อง 100%)</td>
            </tr>
            <tr>
                <td><strong>ภาษาผลลัพธ์</strong></td>
                <td><strong>ภาษาไทย (Thai Language)</strong> ทั้งชื่องานย่อย (task_title) และคำอธิบาย (description)</td>
            </tr>
            <tr>
                <td><strong>บทบาทการทำงาน</strong></td>
                <td>
                    1. รับหัวข้อการบ้าน + คำอธิบาย + กำหนดส่งจริงจาก Classroom<br>
                    2. แตกขั้นตอนการทำงานออกเป็น 3-7 ข้อย่อยเรียงตามลำดับ (Sequential Subtasks)<br>
                    3. ประเมินเวลาทำงานที่สมเหตุสมผล (estimated_hours)<br>
                    4. กำหนดระดับความสำคัญ (HIGH / MEDIUM / LOW) และคำนวณวันกำหนดส่งย่อย
                </td>
            </tr>
        </table>
    </div>

    <div class="no-break">
        <h3>2.2 โมเดลสำรอง (Fallback LLM Engine): Google Gemini 1.5 Flash</h3>
        <table>
            <tr>
                <th style="width: 30%;">พารามิเตอร์</th>
                <th style="width: 70%;">การกำหนดค่า (Configuration)</th>
            </tr>
            <tr>
                <td><strong>Model Identifier</strong></td>
                <td><code>gemini-1.5-flash</code> (รองรับผ่าน Google GenAI SDK หรือ REST API)</td>
            </tr>
            <tr>
                <td><strong>ผู้พัฒนา</strong></td>
                <td>Google DeepMind</td>
            </tr>
            <tr>
                <td><strong>บทบาท</strong></td>
                <td>ทำงานเป็น Fallback อัตโนมัติเมื่อกำหนดค่า <code>AI_PROVIDER=gemini</code> หรือเมื่อระบบต้องการทางเลือกสำรองความเร็วสูง</td>
            </tr>
        </table>
    </div>

    <div class="highlight-card">
        <strong>กลไก Automated Validation Loop:</strong><br>
        หลังจาก AI สร้างแผนงานออกมา ระบบจะรันการตรวจสอบ 3 มิติ (Completeness, Logic Flow & Circular Dependencies, Timeline Limits) หากตรวจพบข้อผิดพลาด ระบบจะส่ง Feedback ย้อนกลับไปให้ AI แก้ไขอัตโนมัติ (Retry สูงสุด 3 ครั้ง) เพื่อให้มั่นใจว่าแผนงานมีคุณภาพสูงสุดก่อนส่งถึงมือนักศึกษา
    </div>

    <div class="page-break"></div>

    <!-- Section 3 -->
    <h2><span class="section-num">3</span> คำอธิบายผลลัพธ์จากแต่ละ API (API Responses & Outputs)</h2>
    <p>รายละเอียดของโครงสร้างข้อมูล (Payload Structure) และผลลัพธ์จริงที่ระบบส่งกลับมาจากแต่ละบริการ:</p>

    <!-- 3.1 Google Classroom -->
    <div class="no-break">
        <h3>3.1 ผลลัพธ์จาก Google Classroom API</h3>
        <p>ส่งข้อมูลการบ้านที่ได้รับมอบหมายออกมาเป็น JSON Array ของ Assignment Objects:</p>
        <pre>{{
  "id": "896521045888",
  "course_id": "896495436708",
  "course_name": "Test-elev8-v1",
  "title": "ออกแบบโลโก้หลักการ Gestalt",
  "description": "ให้นักศึกษาออกแบบโลโก้โดยประยุกต์ใช้หลักการจิตวิทยา Gestalt พร้อมอธิบายแนวคิด",
  "due_date": "2026-11-30 16:59:00",
  "alternate_link": "https://classroom.google.com/c/ODk2NDk1NDM2NzA4/a/ODk2NTIxMDQ1ODg4/details",
  "is_processed": false
}}</pre>
        <p><strong>คำอธิบายฟิลด์สำคัญ:</strong></p>
        <ul>
            <li><code>id</code>: รหัสอ้างอิงการบ้านจริงจาก Google Classroom (นำไปใช้เป็น Parent ID ในฐานข้อมูล)</li>
            <li><code>due_date</code>: กำหนดส่งที่แปลงเป็นรูปแบบมาตรฐาน <code>YYYY-MM-DD HH:MM:SS</code> เรียบร้อยแล้ว</li>
            <li><code>is_processed</code>: ตัวระบุสถานะว่าการบ้านชิ้นนี้เคยถูกสร้างแผนงานและบันทึกลงระบบแล้วหรือไม่</li>
        </ul>
    </div>

    <!-- 3.2 AI & n8n Output -->
    <div class="no-break">
        <h3>3.2 ผลลัพธ์จาก AI & n8n Webhook API (Project Blueprint)</h3>
        <p>โครงสร้างแผนงานที่ AI แตกออกมาเป็นภาษาไทย พร้อมผ่านการตรวจสอบความถูกต้องแล้ว:</p>
        <pre>{{
  "status": "success",
  "assignment_id": "896521045888",
  "project_name": "ออกแบบโลโก้หลักการ Gestalt",
  "blueprint": {{
    "project_id": "896521045888",
    "project_summary": "สรุปแผนงาน: เริ่มต้นจากการค้นคว้าหลักจิตวิทยา Gestalt ร่างไอเดีย และจัดทำไฟล์โลโก้ส่งอาจารย์",
    "total_estimated_hours": 12.5,
    "subtasks": [
      {{
        "task_order": 1,
        "task_title": "ศึกษาและค้นคว้าหลักการ Gestalt",
        "description": "ค้นคว้าทฤษฎี Gestalt Psychology เช่น Proximity, Similarity, Continuity และรวบรวมตัวอย่าง",
        "priority": "HIGH",
        "estimated_hours": 3.0,
        "suggested_due_date": "2026-11-05 18:00:00",
        "status": "TODO"
      }},
      {{
        "task_order": 2,
        "task_title": "สเก็ตช์และระดมไอเดียโลโก้",
        "description": "วาดภาพร่างแนวคิดโลโก้อย่างน้อย 3 แบบบนกระดาษหรือแท็บเล็ต",
        "priority": "MEDIUM",
        "estimated_hours": 3.5,
        "suggested_due_date": "2026-11-12 18:00:00",
        "status": "TODO"
      }},
      {{
        "task_order": 3,
        "task_title": "ออกแบบไฟล์เวกเตอร์ดิจิทัล (Digital Vector)",
        "description": "สร้างภาพดิจิทัลด้วย Illustrator/Photoshop พร้อมกำหนด Color Palette",
        "priority": "HIGH",
        "estimated_hours": 4.0,
        "suggested_due_date": "2026-11-20 18:00:00",
        "status": "TODO"
      }},
      {{
        "task_order": 4,
        "task_title": "ตรวจสอบความเรียบร้อยและส่งงาน",
        "description": "Export ไฟล์ PDF/PNG และแนบคำอธิบายแนวคิดส่งผ่าน Google Classroom",
        "priority": "LOW",
        "estimated_hours": 2.0,
        "suggested_due_date": "2026-11-28 16:59:00",
        "status": "TODO"
      }}
    ]
  }},
  "validation": {{
    "is_valid": true,
    "retry_count": 1,
    "errors": []
  }}
}}</pre>
    </div>

    <div class="page-break"></div>

    <!-- 3.3 Google Sheets Data Structure -->
    <div class="no-break">
        <h3>3.3 ผลลัพธ์ใน Google Sheets Database (โครงสร้างตารางข้อมูลจริง)</h3>
        <p>ข้อมูลทั้งหมดถูกจัดเก็บบน Google Spreadsheet ID: <code>1pYAR9Uqec80dKSRvHt8pStGBcxJlbf62RfAFvNSToSI</code> แบ่งออกเป็น 3 แท็บข้อมูล:</p>
        
        <p><strong>1. แท็บ 'Assignments' (ตารางการบ้านหลัก):</strong></p>
        <table>
            <thead>
                <tr>
                    <th>id</th>
                    <th>course_name</th>
                    <th>title</th>
                    <th>due_date</th>
                    <th>status</th>
                    <th>created_at</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><code>896521045888</code></td>
                    <td>Test-elev8-v1</td>
                    <td>ออกแบบโลโก้หลักการ Gestalt</td>
                    <td>2026-11-30 16:59:00</td>
                    <td><span class="badge badge-green">PROCESSED</span></td>
                    <td>2026-10-29 15:13:42</td>
                </tr>
            </tbody>
        </table>

        <p><strong>2. แท็บ 'Subtasks' (ตารางงานย่อยสำหรับ Checklist & Dashboard):</strong></p>
        <table>
            <thead>
                <tr>
                    <th>id</th>
                    <th>assignment_id</th>
                    <th>order</th>
                    <th>task_title</th>
                    <th>priority</th>
                    <th>hours</th>
                    <th>status</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><code>896521045888_1</code></td>
                    <td>896521045888</td>
                    <td>1</td>
                    <td>ศึกษาและค้นคว้าหลักการ Gestalt</td>
                    <td>HIGH</td>
                    <td>3.0</td>
                    <td><span class="badge badge-green">DONE</span></td>
                </tr>
                <tr>
                    <td><code>896521045888_2</code></td>
                    <td>896521045888</td>
                    <td>2</td>
                    <td>สเก็ตช์และระดมไอเดียโลโก้</td>
                    <td>MEDIUM</td>
                    <td>3.5</td>
                    <td><span class="badge badge-yellow">TODO</span></td>
                </tr>
                <tr>
                    <td><code>896521045888_3</code></td>
                    <td>896521045888</td>
                    <td>3</td>
                    <td>ออกแบบไฟล์เวกเตอร์ดิจิทัล</td>
                    <td>HIGH</td>
                    <td>4.0</td>
                    <td><span class="badge badge-yellow">TODO</span></td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- 3.4 Internal Realtime Status Update -->
    <div class="no-break">
        <h3>3.4 ผลลัพธ์จาก Real-time Status Transition API (เมื่อนักศึกษาคลิกติ๊กถูก ✔)</h3>
        <p>เมื่อผู้ใช้กดติ๊กงานย่อยสำเร็จในหน้า Dashboard หรือ Task Detail หน้าเว็บจะยิงคำขอไปยัง Endpoint:</p>
        <p><code>POST /api/subtasks/896521045888_1/status</code> พร้อม Payload <code>{{"status": "DONE"}}</code></p>
        <p><strong>ผลลัพธ์ที่ตอบกลับ:</strong></p>
        <pre>{{
  "success": true,
  "subtask_id": "896521045888_1",
  "new_status": "DONE"
}}</pre>
        <p><strong>พฤติกรรมของระบบ:</strong> เซิร์ฟเวอร์จะอัปเดต Cell คอลัมน์สถานะ (Column J) ใน Google Sheet ให้ทันที และหน้าจอแสดงผลจะขีดฆ่าข้อความ ปรับเปอร์เซ็นต์ความคืบหน้ารวมแบบ Optimistic UI ทันทีใน 0.01 วินาที โดยไม่ต้องรีเฟรชหน้าเว็บ</p>
    </div>

    <div class="footer-note">
        เอกสารฉบับนี้สร้างขึ้นโดยระบบอัตโนมัติของ <strong>ELEV8 AI Planner</strong> &copy; 2026 ทุกสิทธิ์ถูกต้องตามมาตรฐานวิศวกรรมซอฟต์แวร์
    </div>

</body>
</html>"""

    html_file = os.path.abspath('api_documentation.html')
    pdf_file = os.path.abspath('ELEV8_API_and_Model_Documentation.pdf')

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Generated HTML at: {html_file}")

    # Use Chrome Headless to export pixel-perfect PDF
    chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    if not os.path.exists(chrome_path):
        chrome_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

    cmd = [
        chrome_path,
        '--headless',
        '--disable-gpu',
        '--no-pdf-header-footer',
        f'--print-to-pdf={pdf_file}',
        html_file
    ]

    print("Converting HTML to PDF via Chrome/Edge engine...")
    res = subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 1000:
        print(f"SUCCESS: PDF generated successfully at: {pdf_file} ({os.path.getsize(pdf_file)} bytes)")
    else:
        print("Error generating PDF:", res.stderr)

if __name__ == '__main__':
    generate_pdf()

