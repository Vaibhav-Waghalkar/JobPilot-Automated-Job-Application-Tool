import sqlite3

def purge_mock_data():
    conn = sqlite3.connect('data/jobpilot.db')
    c = conn.cursor()

    # 1. Delete all mock/test records from job_applications
    c.execute("""
        DELETE FROM job_applications 
        WHERE platform = 'mock' 
           OR apply_url LIKE '%mock%' 
           OR company IN ('FastAnswer Corp', 'BlockerTest Corp', 'Apex Innovations', 'Global Systems', 'LocalMock Corp')
           OR title LIKE '%Test%'
    """)
    deleted_apps = c.rowcount

    # 2. Delete any mock activity logs and old test run logs
    c.execute("""
        DELETE FROM activity_logs 
        WHERE message LIKE '%mock%' 
           OR message LIKE '%Mock%' 
           OR message LIKE '%FastAnswer%' 
           OR message LIKE '%BlockerTest%' 
           OR message LIKE '%Apex Innovations%' 
           OR message LIKE '%Global Systems%'
           OR message LIKE '%mock_page%'
    """)
    deleted_logs = c.rowcount

    conn.commit()
    print(f"Purged {deleted_apps} mock job applications and {deleted_logs} mock activity logs from real database.")

    # Inspect remaining applications and logs
    c.execute("SELECT id, platform, company, title FROM job_applications")
    apps = c.fetchall()
    print(f"Remaining applications in jobpilot.db: {len(apps)}")
    for a in apps:
        print("  ", a)

    c.execute("SELECT id, message FROM activity_logs ORDER BY id DESC LIMIT 10")
    logs = c.fetchall()
    print(f"Remaining activity logs in jobpilot.db: {len(logs)}")
    for l in logs:
        print("  ", l)

    conn.close()

if __name__ == "__main__":
    purge_mock_data()
