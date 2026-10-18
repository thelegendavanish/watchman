import os
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def add_image_placeholder(doc, title, description, height_in_inches=2.2):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, "F8F9FA")
    set_cell_margins(cell, top=200, bottom=200, left=250, right=250)
    
    # Border
    tcPr = cell._element.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="dashed" w:sz="12" w:space="0" w:color="9AA0A6"/>'
        f'<w:bottom w:val="dashed" w:sz="12" w:space="0" w:color="9AA0A6"/>'
        f'<w:left w:val="dashed" w:sz="12" w:space="0" w:color="9AA0A6"/>'
        f'<w:right w:val="dashed" w:sz="12" w:space="0" w:color="9AA0A6"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    run_tag = p.add_run(f"📷 [ PLACEHOLDER FOR IMAGE / SCREENSHOT ]")
    run_tag.bold = True
    run_tag.font.name = "Calibri"
    run_tag.font.size = Pt(11)
    run_tag.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    p2 = cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(2)
    p2.paragraph_format.space_after = Pt(4)
    run_title = p2.add_run(title)
    run_title.bold = True
    run_title.font.name = "Calibri"
    run_title.font.size = Pt(10.5)
    run_title.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    
    p3 = cell.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.space_before = Pt(0)
    p3.paragraph_format.space_after = Pt(12)
    run_desc = p3.add_run(f"Instructions: {description}")
    run_desc.italic = True
    run_desc.font.name = "Calibri"
    run_desc.font.size = Pt(9.5)
    run_desc.font.color.rgb = RGBColor(0x70, 0x70, 0x70)
    
    # Empty space after table
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(8)

def add_code_block(doc, code_text):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, "2B303A")
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(code_text)
    run.font.name = "Consolas"
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(0xF0, 0xF6, 0xFC)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def add_callout(doc, text, callout_type="note"):
    colors = {
        "note": ("E8F0FE", "1A73E8", "NOTE"),
        "tip": ("E6F4EA", "137333", "PRO TIP"),
        "warning": ("FEF7E0", "B06000", "IMPORTANT WARNING"),
    }
    bg, border_color, label = colors.get(callout_type, ("F1F3F4", "5F6368", "NOTE"))
    
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, bg)
    set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
    
    # Left border only
    tcPr = cell._element.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{border_color}"/>'
        f'<w:top w:val="none"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    
    r_label = p.add_run(f"[{label}] ")
    r_label.bold = True
    r_label.font.name = "Calibri"
    r_label.font.size = Pt(10)
    r_label.font.color.rgb = RGBColor(int(border_color[:2], 16), int(border_color[2:4], 16), int(border_color[4:], 16))
    
    r_text = p.add_run(text)
    r_text.font.name = "Calibri"
    r_text.font.size = Pt(10)
    r_text.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def build_manual():
    doc = docx.Document()
    
    # Page setup - 0.75 in margins
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)
        
    # Styles configuration
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0x26, 0x26, 0x26)
    normal.paragraph_format.line_spacing = 1.2
    normal.paragraph_format.space_after = Pt(6)

    # ─────────────────────────────────────────────────────────────────────────
    # COVER / HEADER
    # ─────────────────────────────────────────────────────────────────────────
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(10)
    p_title.paragraph_format.space_after = Pt(2)
    r_title = p_title.add_run("WATCHMAN")
    r_title.bold = True
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(28)
    r_title.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(6)
    r_sub = p_sub.add_run("Local Windows File Integrity Monitoring & Audit System")
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(15)
    r_sub.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    
    p_doc = doc.add_paragraph()
    p_doc.paragraph_format.space_after = Pt(18)
    r_doc = p_doc.add_run("Comprehensive User Guide & Technical Operations Manual")
    r_doc.bold = True
    r_doc.font.size = Pt(12)
    r_doc.font.color.rgb = RGBColor(0x00, 0x80, 0x80)
    
    # Metadata Block
    t_meta = doc.add_table(rows=4, cols=2)
    t_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_info = [
        ("Software Version:", "0.2.0"),
        ("Target Platform:", "Microsoft Windows 10 & 11 (64-bit)"),
        ("Security Model:", "User-Space execution (No Administrator privileges required)"),
        ("Document Release:", "Production User Manual")
    ]
    for row_idx, (lbl, val) in enumerate(meta_info):
        c0 = t_meta.cell(row_idx, 0)
        c1 = t_meta.cell(row_idx, 1)
        c0.width = Inches(2.2)
        c1.width = Inches(4.3)
        set_cell_background(c0, "F1F4F9")
        set_cell_background(c1, "F8F9FA")
        
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_before = Pt(2)
        p0.paragraph_format.space_after = Pt(2)
        r0 = p0.add_run(lbl)
        r0.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
        
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_before = Pt(2)
        p1.paragraph_format.space_after = Pt(2)
        r1 = p1.add_run(val)
        r1.font.size = Pt(9.5)
        r1.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(12)
    
    # Horizontal rule
    p_hr = doc.add_paragraph()
    p_hr.paragraph_format.space_after = Pt(18)
    r_hr = p_hr.add_run("―" * 55)
    r_hr.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. INTRODUCTION & OVERVIEW
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("1. Executive Summary & Architecture Overview")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    p = doc.add_paragraph(
        "Watchman is a purpose-built, user-controlled file integrity monitoring (FIM) and change auditing utility for Microsoft Windows. "
        "Unlike enterprise security agents that install hidden system-level services, consume background resources, or transmit private data to remote SaaS dashboards, "
        "Watchman is designed strictly around user autonomy, transparency, and data ownership."
    )
    
    p = doc.add_paragraph("Key Architecture Highlights:")
    features = [
        ("Zero Administrative Privileges Required: ", "Runs entirely within standard user rights. It never touches system registry roots, never modifies Windows kernel drivers, and does not require UAC elevation."),
        ("Multi-Deployment Isolation: ", "Define completely isolated monitoring setups (e.g., 'work', 'finance', 'sourcecode'), each with independent directory sets, exclude rules, and local event databases."),
        ("Tamper-Evident SHA-256 Chain Hashing: ", "Every recorded filesystem event stores a cryptographic SHA-256 hash that chains directly into the previous record. Sequential deletions or row modifications are immediately detectable."),
        ("Non-Blocking Concurrent Operations: ", "Disk I/O and file hashing are handled through dedicated background threads (ThreadPoolExecutor and a dedicated SQLite worker thread), guaranteeing real-time responsiveness without locking."),
        ("Baseline Snapshot & Differential Auditing: ", "Take instant point-in-time cryptographic snapshots of entire directory trees, and verify files at any time to catch modified, missing, or unauthorized new files."),
        ("Optional Encrypted Real-Time Alerts: ", "Configurable Telegram bot alerts with credentials secured inside Windows Credential Manager via native DPAPI encryption.")
    ]
    for title, desc in features:
        bp = doc.add_paragraph(style='List Bullet')
        bp.paragraph_format.space_after = Pt(4)
        rt = bp.add_run(title)
        rt.bold = True
        rt.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
        bp.add_run(desc)

    fig1_path = Path("docs/assets/fig1_architecture.jpg")
    if fig1_path.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(10)
        p_img.paragraph_format.space_after = Pt(4)
        r_img = p_img.add_run()
        r_img.add_picture(str(fig1_path), width=Inches(6.5))
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(14)
        r_cap = p_cap.add_run("Figure 1: Watchman High-Level System Architecture")
        r_cap.bold = True
        r_cap.font.name = "Calibri"
        r_cap.font.size = Pt(9.5)
        r_cap.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    else:
        add_image_placeholder(
            doc,
            "Figure 1: Watchman High-Level System Architecture",
            "Paste an architecture diagram showing the relationship between Watched Folders, Watchdog Observer, SQLite Worker Thread, Hash Engine, and Telegram/CLI outputs."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. SYSTEM REQUIREMENTS & PREREQUISITES
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("2. System Requirements & Prerequisites")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    p = doc.add_paragraph("Before installing Watchman, ensure your Windows workstation meets the following prerequisites:")
    
    t_req = doc.add_table(rows=5, cols=3)
    t_req.alignment = WD_TABLE_ALIGNMENT.CENTER
    req_headers = ["Component", "Minimum Requirement", "Recommended"]
    req_data = [
        ["Operating System", "Windows 10 (Build 19041+) or Windows 11", "Windows 11 (64-bit)"],
        ["Python Runtime", "Python 3.10+", "Python 3.12 or 3.13 (64-bit)"],
        ["Shell Environment", "Windows PowerShell 5.1", "PowerShell 7 (pwsh) or Windows Terminal"],
        ["User Permissions", "Standard User Account", "Standard User Account (No Admin needed)"]
    ]
    # Header row
    for col_idx, h in enumerate(req_headers):
        cell = t_req.cell(0, col_idx)
        set_cell_background(cell, "1F4E79")
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(9.5)
        
    for row_idx, data_row in enumerate(req_data, start=1):
        bg = "FFFFFF" if row_idx % 2 != 0 else "F8F9FA"
        for col_idx, text in enumerate(data_row):
            cell = t_req.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            r = p.add_run(text)
            r.font.size = Pt(9)
            if col_idx == 0:
                r.bold = True
                
    doc.add_paragraph().paragraph_format.space_after = Pt(8)
    add_callout(doc, "When installing Python from python.org, you MUST select the checkbox labeled 'Add python.exe to PATH' during setup to ensure terminal accessibility.", "warning")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. INSTALLATION & SETUP
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("3. Installation Guide")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    doc.add_heading(level=2).add_run("3.1 Method A: Remote Terminal Installer (Recommended)").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph(
        "The fastest and cleanest way to install Watchman is using PowerShell's native Invoke-RestMethod ('irm | iex') pipeline. "
        "Open a PowerShell terminal as your normal user and execute:"
    )
    add_code_block(doc, "irm https://raw.githubusercontent.com/thelegendavanish/watchman/main/install.ps1 | iex")
    doc.add_paragraph(
        "The remote installer automatically verifies Python version compatibility, downloads the official repository release, "
        "installs Watchman into your user site-packages via pip, and registers the 'watchman' binary onto your PATH."
    )
    
    add_image_placeholder(
        doc,
        "Figure 2: Successful PowerShell Installation Output",
        "Paste a screenshot of your PowerShell terminal running the irm | iex installer and displaying the green [OK] installation confirmation."
    )

    doc.add_heading(level=2).add_run("3.2 Method B: Manual Offline Installation").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("If you are working in an air-gapped or offline environment, clone or extract the repository and run:")
    add_code_block(doc, "cd C:\\path\\to\\watchman\npython -m pip install --user .\n\n# Optional: Windows Credential Manager support\npython -m pip install --user \".[secure]\"")

    doc.add_heading(level=2).add_run("3.3 Verifying the Installation").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("Verify that Watchman is properly recognized by opening a fresh PowerShell session and executing:")
    add_code_block(doc, "watchman --help")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. CONFIGURING DEPLOYMENTS & WATCH PATHS
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("4. Configuring Deployments & Watched Directories")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    doc.add_paragraph(
        "Watchman organizes all monitoring targets into independent named 'deployments'. "
        "Each deployment stores its configuration, baseline snapshots, event logs, and daemon state in an isolated directory located under:"
    )
    add_code_block(doc, "%LOCALAPPDATA%\\Watchman\\deployments\\<deployment-name>\\\n    config.json       <- Protected paths, exclude patterns, startup flags\n    events.sqlite3    <- Tamper-evident chain-hashed SQLite event log\n    monitor.pid       <- Active daemon PID tracking file\n    monitor.log       <- Daemon standard output & error log")

    doc.add_heading(level=2).add_run("4.1 Initializing a Deployment").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("To create a new deployment called 'secure-docs':")
    add_code_block(doc, "watchman init secure-docs")
    add_callout(doc, "Initializing a deployment only creates the database schema and configuration file. It does NOT start monitoring and does NOT alter Windows startup.", "note")

    doc.add_heading(level=2).add_run("4.2 Adding Folders to Protect").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("Add one or more directories to be continuously watched for file modifications, creations, deletions, or moves:")
    add_code_block(doc, 'watchman watch add secure-docs "C:\\Users\\YourName\\Documents"\nwatchman watch add secure-docs "D:\\CriticalProjects"')

    doc.add_heading(level=2).add_run("4.3 Applying File Exclusion Patterns").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph(
        "To filter out noisy temporary files generated by office suites or text editors, pass repeatable '--exclude' glob patterns:"
    )
    add_code_block(doc, 'watchman watch add secure-docs "D:\\SourceCode" --exclude "*.tmp" --exclude "~$*" --exclude "*.log"')

    doc.add_heading(level=2).add_run("4.4 Listing and Removing Watched Paths").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("Inspect all active directories and exclusion rules configured for a deployment:")
    add_code_block(doc, "watchman watch list secure-docs\n\n# To remove a watched path:\nwatchman watch remove secure-docs \"D:\\CriticalProjects\"")

    add_image_placeholder(
        doc,
        "Figure 3: Deployment Initialization and Directory Configuration",
        "Paste a screenshot showing 'watchman init' followed by 'watchman watch add' with exclusions and 'watchman watch list'."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 5. BASELINE SCAN & INTEGRITY VERIFICATION
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("5. Baseline Cryptographic Integrity Auditing")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    doc.add_paragraph(
        "In addition to real-time event streaming, Watchman provides an offline integrity engine. "
        "A baseline scan takes an immediate SHA-256 fingerprint snapshot of every file inside your protected directories. "
        "You can run an integrity verification at any point in time to detect unauthorized tampering."
    )

    doc.add_heading(level=2).add_run("5.1 Taking a Baseline Snapshot").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    add_code_block(doc, "watchman scan secure-docs")
    doc.add_paragraph("Watchman recursively crawls every watched directory, computes SHA-256 digests, and stores them in the local 'baselines' table.")

    doc.add_heading(level=2).add_run("5.2 Verifying Integrity Against Baseline").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("Run verification periodically or via scheduled tasks:")
    add_code_block(doc, "watchman verify secure-docs")
    doc.add_paragraph("If all files match the baseline, Watchman returns exit code 0:")
    add_code_block(doc, "Verifying integrity for deployment 'secure-docs'...\n[OK] All files match the baseline. No changes detected.")
    
    doc.add_paragraph("If discrepancies exist, Watchman lists exact findings and exits with code 1:")
    add_code_block(doc, "[WARNING] 3 discrepancy(ies) found:\n\n  MODIFIED  C:\\Users\\YourName\\Documents\\payroll.xlsx\n            expected : 3a51f8b76e...\n            actual   : 9f12d4a8bc...\n  MISSING   C:\\Users\\YourName\\Documents\\secret.key\n  NEW       C:\\Users\\YourName\\Documents\\malware.exe\n            sha256   : e3b0c44298...")

    add_image_placeholder(
        doc,
        "Figure 4: Baseline Integrity Scan & Verification Workflow",
        "Paste a screenshot showing 'watchman scan' indexing files and 'watchman verify' reporting modified or clean state."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 6. RUNNING THE MONITOR (FOREGROUND & BACKGROUND DAEMON)
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("6. Live File Monitoring & Process Management")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    doc.add_heading(level=2).add_run("6.1 Foreground Monitoring Mode").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("To monitor events interactively in your current console (ideal for testing):")
    add_code_block(doc, "watchman start secure-docs")
    doc.add_paragraph("Watchman prints real-time events as they occur. Press Ctrl+C at any time to safely shut down the observer.")

    doc.add_heading(level=2).add_run("6.2 Background Daemon Mode").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph(
        "To detach Watchman and keep it running silently in the background while freeing your terminal:"
    )
    add_code_block(doc, "watchman start secure-docs --background")
    doc.add_paragraph(
        "Watchman launches a detached Windows process group via kernel32 APIs, writes the process ID to 'monitor.pid', "
        "and redirects all daemon output to 'monitor.log'."
    )

    doc.add_heading(level=2).add_run("6.3 Checking Daemon Status").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    add_code_block(doc, "watchman status secure-docs\n\n# Output:\n# Deployment 'secure-docs': RUNNING (PID 14220)\n# Log file: C:\\Users\\...\\monitor.log")
    doc.add_paragraph("You can also view all deployments at once:")
    add_code_block(doc, "watchman list\n\n# Output:\n# secure-docs: 2 protected path(s); startup=disabled [RUNNING]\n# finance: 1 protected path(s); startup=disabled")

    doc.add_heading(level=2).add_run("6.4 Stopping the Background Daemon").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("To gracefully terminate a running background daemon:")
    add_code_block(doc, "watchman stop secure-docs")

    add_image_placeholder(
        doc,
        "Figure 5: Background Daemon Management & Status Checking",
        "Paste a screenshot showing 'watchman start --background', 'watchman status', and 'watchman stop'."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 7. EVENT AUDIT LOGS & EXPORTING
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("7. Event Audit Logs & Data Export")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    doc.add_heading(level=2).add_run("7.1 Viewing Live Event History").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    add_code_block(doc, "watchman logs secure-docs --limit 30")
    doc.add_paragraph("Displays the most recent events in reverse chronological order, including timestamp, action, file path, and SHA-256 hash.")

    doc.add_heading(level=2).add_run("7.2 Exporting Audit Logs to JSON or CSV").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("Export the complete tamper-evident audit trail for reporting or ingestion into SIEM tools:")
    add_code_block(doc, "# Export to JSON\nwatchman export secure-docs --format json --output audit_report.json\n\n# Export to CSV (compatible with Excel & PowerBI)\nwatchman export secure-docs --format csv --output audit_report.csv")

    doc.add_heading(level=2).add_run("7.3 Clearing Event Logs").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("To purge the event table (with interactive safety prompt):")
    add_code_block(doc, "watchman clear secure-docs\n\n# Or bypass prompt in automated scripts:\nwatchman clear secure-docs --yes")

    add_image_placeholder(
        doc,
        "Figure 6: Audit Log Inspection and CSV Export Opened in Excel",
        "Paste a screenshot of 'watchman logs' output and the exported CSV file opened in Microsoft Excel showing chain hashes."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 8. TELEGRAM NOTIFICATIONS
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("8. Real-Time Telegram Security Alerts")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    doc.add_paragraph(
        "Watchman can dispatch instant mobile alerts over Telegram whenever a critical file event occurs. "
        "Credentials are cryptographically stored in Windows Credential Manager using Windows DPAPI."
    )
    doc.add_heading(level=2).add_run("8.1 Configuring Telegram Alerts").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    doc.add_paragraph("Obtain a bot token from @BotFather on Telegram, get your user or group chat ID, and run:")
    add_code_block(doc, 'watchman telegram secure-docs --token "123456789:ABCdefGHIjklMNO" --chat-id "987654321"')

    doc.add_heading(level=2).add_run("8.2 Removing Stored Telegram Credentials").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    add_code_block(doc, "watchman telegram-clear secure-docs")

    add_image_placeholder(
        doc,
        "Figure 7: Real-Time Telegram Alert on Mobile / Desktop App",
        "Paste a screenshot of a real Telegram notification showing event type, modified path, timestamp, and SHA-256 fingerprint."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 9. WINDOWS LOGON STARTUP
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("9. Automatic Windows Logon Startup (Opt-In)")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    doc.add_paragraph(
        "Watchman avoids hidden persistence mechanisms. If you choose to enable automatic monitoring at user logon, "
        "Watchman places a visible, user-accessible '.cmd' shortcut inside your standard Windows Startup directory:"
    )
    add_code_block(doc, "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\Watchman-<deployment>.cmd")

    doc.add_heading(level=2).add_run("9.1 Startup Commands").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    add_code_block(doc, "# Enable monitoring on logon\nwatchman startup enable secure-docs\n\n# Check current startup status\nwatchman startup status secure-docs\n\n# Disable logon startup\nwatchman startup disable secure-docs")

    # ─────────────────────────────────────────────────────────────────────────
    # 10. COMPLETE UNINSTALLATION
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("10. Complete System Uninstallation")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    doc.add_paragraph(
        "Watchman respects clean software uninstallation. When uninstalled, it leaves zero orphan files, services, or registry keys."
    )
    doc.add_heading(level=2).add_run("10.1 Automated One-Liner Removal").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    add_code_block(doc, "irm https://raw.githubusercontent.com/thelegendavanish/watchman/main/uninstall.ps1 | iex")

    doc.add_heading(level=2).add_run("10.2 Manual Removal Steps").font.color.rgb = RGBColor(0x2F, 0x55, 0x97)
    add_code_block(doc, "# 1. Uninstall pip package\npython -m pip uninstall -y watchman\n\n# 2. Delete configuration and database files\nRemove-Item -Recurse -Force \"$env:LOCALAPPDATA\\Watchman\"\n\n# 3. Clean startup shortcuts\nRemove-Item -Force \"$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\Watchman-*.cmd\"")

    add_image_placeholder(
        doc,
        "Figure 8: Uninstaller Clean Confirmation Screen",
        "Paste a screenshot of the uninstaller completing and confirming all databases, daemons, and packages were purged."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 11. COMMAND REFERENCE CHEAT SHEET
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("11. Complete Command Reference Cheat Sheet")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    headers = ["Command Syntax", "Category", "Description"]
    rows = [
        ["watchman init <name>", "Management", "Initialize a new isolated deployment."],
        ["watchman list", "Management", "List all deployments and active daemon status badges."],
        ["watchman watch add <name> <dir>", "Configuration", "Add a directory to the protected monitoring list."],
        ["watchman watch add ... --exclude <pat>", "Configuration", "Exclude specific file glob patterns (e.g. *.tmp)."],
        ["watchman watch remove <name> <dir>", "Configuration", "Remove a directory from the protected list."],
        ["watchman watch list <name>", "Configuration", "Display all protected paths and exclude rules."],
        ["watchman scan <name>", "Integrity", "Take an offline SHA-256 baseline snapshot of all files."],
        ["watchman verify <name>", "Integrity", "Compare current filesystem against baseline snapshot."],
        ["watchman start <name>", "Execution", "Start real-time monitoring in the foreground."],
        ["watchman start <name> --background", "Execution", "Spawn detached background daemon process."],
        ["watchman status <name>", "Execution", "Check if background daemon is active and print PID."],
        ["watchman stop <name>", "Execution", "Gracefully terminate active background daemon."],
        ["watchman logs <name> [--limit N]", "Auditing", "View recent recorded events with timestamps & hashes."],
        ["watchman export <name> --format json|csv", "Auditing", "Export complete tamper-evident audit trail."],
        ["watchman clear <name> [--yes]", "Auditing", "Permanently delete recorded events."],
        ["watchman telegram <name> --token --chat-id", "Alerting", "Store encrypted Telegram bot credentials."]
    ]
    ref_table = doc.add_table(rows=len(rows) + 1, cols=3)
    for col_idx, h in enumerate(headers):
        cell = ref_table.cell(0, col_idx)
        set_cell_background(cell, "1F4E79")
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        r.font.size = Pt(9.5)

    for row_idx, r_data in enumerate(rows, start=1):
        bg = "FFFFFF" if row_idx % 2 != 0 else "F8F9FA"
        for col_idx, text in enumerate(r_data):
            cell = ref_table.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            r = p.add_run(text)
            r.font.size = Pt(8.5)
            if col_idx == 0:
                r.font.name = "Consolas"
                r.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # ─────────────────────────────────────────────────────────────────────────
    # 12. FREQUENTLY ASKED QUESTIONS (FAQ)
    # ─────────────────────────────────────────────────────────────────────────
    h1 = doc.add_heading(level=1)
    r = h1.add_run("12. Troubleshooting & Frequently Asked Questions")
    r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    faqs = [
        ("Q: Does Watchman consume heavy CPU while monitoring large folders?",
         "A: No. Watchman relies on the native Windows ReadDirectoryChangesW API via the Python 'watchdog' library. It uses zero polling overhead. File hashing is dispatched asynchronously into a worker thread pool (max 4 threads), meaning your system remains fast and responsive."),
        ("Q: What happens if a file is modified while the system is turned off?",
         "A: Real-time event hooks only catch events that occur while the monitor is active. For offline changes, run 'watchman verify <name>' periodically. The baseline verification checks every file against the original cryptographic snapshot and immediately catches offline changes."),
        ("Q: Where are my Telegram credentials saved?",
         "A: When the optional 'keyring' module is installed, tokens are stored inside Windows Credential Manager under the service name 'Watchman'. They are encrypted using your Windows user DPAPI master key and never saved in plain text."),
        ("Q: What does 'prev_event_hash' mean in the database?",
         "A: To prevent adversaries from secretly deleting audit rows from the SQLite database, each event incorporates the SHA-256 hash of the immediately preceding event row. If any historical row is altered or deleted, the cryptographic hash chain breaks, proving evidence tampering.")
    ]
    for q, a in faqs:
        pq = doc.add_paragraph()
        pq.paragraph_format.space_before = Pt(4)
        pq.paragraph_format.space_after = Pt(2)
        rq = pq.add_run(q)
        rq.bold = True
        rq.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
        
        pa = doc.add_paragraph()
        pa.paragraph_format.space_before = Pt(0)
        pa.paragraph_format.space_after = Pt(6)
        pa.add_run(a)

    # Save output
    output_path = Path("Watchman_User_Manual.docx").resolve()
    try:
        doc.save(str(output_path))
        print(f"User manual generated successfully at: {output_path}")
    except PermissionError:
        alt_path = Path("Watchman_User_Manual_v2.docx").resolve()
        doc.save(str(alt_path))
        print(f"Note: 'Watchman_User_Manual.docx' is currently open in Word. Saved updated manual with Figure 1 to: {alt_path}")

if __name__ == "__main__":
    build_manual()
