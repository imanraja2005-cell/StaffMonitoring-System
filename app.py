from flask import Flask, render_template, request, redirect, url_for, send_file
import os
import sqlite3
from datetime import date, datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)

app = Flask(__name__)
app.secret_key = "staff_monitoring_secret"

DATABASE = "staff.db"

staff_users = {
    "Mr.A.Charles": "Charles123",
    "Dr.J.Hirudhaya Mary Asha": "Asha123",
    "Mr.C.Mohanraja": "Mohan123",
    "Mr.M.Jesudoss": "Jesudoss123",
    "Dr.S.Josephine Theresa": "Josephine123"
}


# Database Connection
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize Database
def initialize_database():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (staff_id) REFERENCES staff(id),
            UNIQUE(staff_id, attendance_date)
        )
    """)

    conn.commit()
    conn.close()


# Login
@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if username == "Mr.A.Charles" and password == "Charles123":
            return redirect(url_for("admin"))

        elif username in staff_users and staff_users[username] == password:
            return redirect(url_for("staff"))

        return "Invalid Username or Password"

    return render_template("login.html")


# Admin Dashboard
@app.route("/admin")
def admin():

    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM staff"
    ).fetchone()[0]

    present = conn.execute(
        "SELECT COUNT(*) FROM staff WHERE status='Present'"
    ).fetchone()[0]

    absent = conn.execute(
        "SELECT COUNT(*) FROM staff WHERE status='Absent'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total=total,
        present=present,
        absent=absent
    )


# Staff Dashboard
@app.route("/staff")
def staff():
    return render_template("staff.html")


# Staff Management
@app.route("/staff_management")
def staff_management():

    conn = get_db()

    staff_list = conn.execute(
        "SELECT * FROM staff ORDER BY id"
    ).fetchall()

    conn.close()

    return render_template(
        "staff_management.html",
        staff=staff_list
    )


# Add Staff
@app.route("/add_staff", methods=["POST"])
def add_staff():

    name = request.form["name"].strip()
    department = request.form["department"].strip()
    status = request.form["status"]

    if not name or not department:
        return "Please enter all staff details"

    conn = get_db()

    conn.execute(
        "INSERT INTO staff (name, department, status) VALUES (?, ?, ?)",
        (name, department, status)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("staff_management"))


# Edit Staff
@app.route("/edit_staff/<int:id>", methods=["GET", "POST"])
def edit_staff(id):

    conn = get_db()

    if request.method == "POST":

        name = request.form["name"].strip()
        department = request.form["department"].strip()
        status = request.form["status"]

        if not name or not department:
            conn.close()
            return "Please enter all staff details"

        conn.execute(
            """UPDATE staff
               SET name=?, department=?, status=?
               WHERE id=?""",
            (name, department, status, id)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("staff_management"))

    staff_member = conn.execute(
        "SELECT * FROM staff WHERE id=?",
        (id,)
    ).fetchone()

    conn.close()

    if staff_member is None:
        return "Staff not found", 404

    return render_template(
        "edit_staff.html",
        staff=staff_member
    )


# Delete Staff
@app.route("/delete_staff/<int:id>")
def delete_staff(id):

    conn = get_db()

    conn.execute(
        "DELETE FROM attendance WHERE staff_id=?",
        (id,)
    )

    conn.execute(
        "DELETE FROM staff WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("staff_management"))


# Attendance Management
@app.route("/attendance", methods=["GET", "POST"])
def attendance():

    if request.method == "POST":

        staff_id = request.form["staff_id"]
        attendance_date = request.form["attendance_date"]
        status = request.form["status"]

        if status not in ["Present", "Absent"]:
            return "Invalid attendance status", 400

        conn = get_db()

        staff_member = conn.execute(
            "SELECT id FROM staff WHERE id=?",
            (staff_id,)
        ).fetchone()

        if staff_member is None:
            conn.close()
            return "Staff not found", 404

        conn.execute("""
            INSERT INTO attendance
            (staff_id, attendance_date, status)
            VALUES (?, ?, ?)
            ON CONFLICT(staff_id, attendance_date)
            DO UPDATE SET status=excluded.status
        """, (staff_id, attendance_date, status))

        conn.commit()
        conn.close()

        return redirect(
            url_for("attendance", date=attendance_date)
        )

    selected_date = request.args.get(
        "date", date.today().isoformat()
    )

    conn = get_db()

    staff_list = conn.execute(
        "SELECT * FROM staff ORDER BY name"
    ).fetchall()

    attendance_records = conn.execute("""
        SELECT
            attendance.id,
            staff.name,
            staff.department,
            attendance.attendance_date,
            attendance.status
        FROM attendance
        JOIN staff ON attendance.staff_id = staff.id
        WHERE attendance.attendance_date=?
        ORDER BY staff.name
    """, (selected_date,)).fetchall()

    conn.close()

    return render_template(
        "attendance.html",
        staff=staff_list,
        attendance_records=attendance_records,
        selected_date=selected_date
    )


# Reports
@app.route("/reports")
def reports():

    selected_month = request.args.get(
        "month", date.today().strftime("%Y-%m")
    )

    try:
        datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        return "Invalid month format", 400

    conn = get_db()

    total_staff = conn.execute(
        "SELECT COUNT(*) FROM staff"
    ).fetchone()[0]

    present = conn.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE status='Present'
        AND strftime('%Y-%m', attendance_date)=?
    """, (selected_month,)).fetchone()[0]

    absent = conn.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE status='Absent'
        AND strftime('%Y-%m', attendance_date)=?
    """, (selected_month,)).fetchone()[0]

    total_marked = present + absent

    percentage = (
        round((present / total_marked) * 100, 1)
        if total_marked > 0 else 0
    )

    records = conn.execute("""
        SELECT
            attendance.id,
            staff.name,
            staff.department,
            attendance.attendance_date,
            attendance.status
        FROM attendance
        JOIN staff ON attendance.staff_id = staff.id
        WHERE strftime('%Y-%m', attendance.attendance_date)=?
        ORDER BY attendance.attendance_date DESC, staff.name
    """, (selected_month,)).fetchall()

    conn.close()

    return render_template(
        "reports.html",
        total_staff=total_staff,
        present=present,
        absent=absent,
        percentage=percentage,
        records=records,
        selected_month=selected_month
    )


# Download Monthly Attendance PDF
@app.route("/download_report")
def download_report():

    selected_month = request.args.get(
        "month", date.today().strftime("%Y-%m")
    )

    try:
        month_date = datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        return "Invalid month format", 400

    conn = get_db()

    total_staff = conn.execute(
        "SELECT COUNT(*) FROM staff"
    ).fetchone()[0]

    present = conn.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE status='Present'
        AND strftime('%Y-%m', attendance_date)=?
    """, (selected_month,)).fetchone()[0]

    absent = conn.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE status='Absent'
        AND strftime('%Y-%m', attendance_date)=?
    """, (selected_month,)).fetchone()[0]

    total_marked = present + absent

    percentage = (
        round((present / total_marked) * 100, 1)
        if total_marked > 0 else 0
    )

    records = conn.execute("""
        SELECT
            staff.name,
            staff.department,
            attendance.attendance_date,
            attendance.status
        FROM attendance
        JOIN staff ON attendance.staff_id = staff.id
        WHERE strftime('%Y-%m', attendance.attendance_date)=?
        ORDER BY attendance.attendance_date DESC, staff.name
    """, (selected_month,)).fetchall()

    conn.close()

    # Create PDF in memory
    pdf_buffer = BytesIO()

    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    college_style = ParagraphStyle(
        "CollegeName",
        parent=styles["Normal"],
        fontSize=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1E293B"),
        fontName="Helvetica-Bold",
        spaceAfter=5
    )

    department_style = ParagraphStyle(
        "DepartmentName",
        parent=styles["Normal"],
        fontSize=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12
    )

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4338CA"),
        spaceAfter=10
    )

    normal_style = styles["Normal"]

    elements = []

    # College Logo
    logo_path = os.path.join(
        app.root_path, "static", "college_logo.jpg"
    )

    if os.path.exists(logo_path):
        college_logo = Image(
            logo_path,
            width=28 * mm,
            height=28 * mm,
            kind="proportional"
        )

        college_logo.hAlign = "CENTER"

        elements.append(college_logo)
        elements.append(Spacer(1, 8))

    # College Heading
    elements.append(
        Paragraph("ST. JOSEPH'S COLLEGE", college_style)
    )

    elements.append(
        Paragraph(
            "Department of Artificial Intelligence and Machine Learning",
            department_style
        )
    )

    elements.append(
        Paragraph("STAFF ATTENDANCE REPORT", title_style)
    )

    elements.append(
        Paragraph(
            f"Monthly Attendance Summary - {month_date.strftime('%B %Y')}",
            ParagraphStyle(
                "Subtitle",
                parent=normal_style,
                alignment=TA_CENTER,
                fontSize=12
            )
        )
    )

    elements.append(Spacer(1, 12))

    # Monthly Summary
    summary_data = [
        ["Total Staff", "Present", "Absent", "Attendance %"],
        [
            str(total_staff),
            str(present),
            str(absent),
            f"{percentage}%"
        ]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[42 * mm, 42 * mm, 42 * mm, 42 * mm]
    )

    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4338CA")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EEF2FF")),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9)
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Attendance Details
    elements.append(
        Paragraph("Attendance Details", styles["Heading2"])
    )

    table_data = [[
        "S.No",
        "Staff Name",
        "Department",
        "Date",
        "Status"
    ]]

    for index, record in enumerate(records, start=1):
        table_data.append([
            str(index),
            Paragraph(str(record["name"]), normal_style),
            Paragraph(str(record["department"]), normal_style),
            str(record["attendance_date"]),
            str(record["status"])
        ])

    if not records:
        table_data.append([
            "-", "No attendance records",
            "-", "-", "-"
        ])

    attendance_table = Table(
        table_data,
        colWidths=[13 * mm, 48 * mm, 43 * mm, 35 * mm, 31 * mm],
        repeatRows=1
    )

    attendance_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4338CA")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 1), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#EEF2FF")]),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
    ]))

    elements.append(attendance_table)

    elements.append(Spacer(1, 18))

    # Footer
    elements.append(
        Paragraph(
            "Generated by Staff Monitoring System",
            ParagraphStyle(
                "Footer",
                parent=normal_style,
                alignment=TA_CENTER,
                fontSize=8,
                textColor=colors.grey
            )
        )
    )

    doc.build(elements)

    pdf_buffer.seek(0)

    filename = f"Attendance_Report_{selected_month}.pdf"

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


# Logout
@app.route("/logout")
def logout():
    return redirect(url_for("login"))


# Run Application
if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)