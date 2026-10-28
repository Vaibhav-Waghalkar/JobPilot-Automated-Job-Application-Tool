import sqlite3

conn = sqlite3.connect('data/jobpilot.db')
c = conn.cursor()

# Check mock or test platform applications
c.execute("SELECT id, company, title, platform, status FROM job_applications WHERE platform = 'mock' OR company IN ('FastAnswer Corp', 'BlockerTest Corp', 'Apex Innovations', 'Global Systems')")
rows = c.fetchall()
print(f"Found {len(rows)} mock records to delete:")
for r in rows:
    print(" ", r)

# Delete all mock/test records from job_applications
c.execute("DELETE FROM job_applications WHERE platform = 'mock' OR company IN ('FastAnswer Corp', 'BlockerTest Corp', 'Apex Innovations', 'Global Systems')")
deleted_apps = c.rowcount

# Delete any mock activity logs
c.execute("DELETE FROM activity_logs WHERE message LIKE '%FastAnswer%' OR message LIKE '%BlockerTest%' OR message LIKE '%Apex Innovations%' OR message LIKE '%Global Systems%'")
deleted_logs = c.rowcount

conn.commit()
print(f"Deleted {deleted_apps} mock job applications and {deleted_logs} mock activity logs.")

# Remaining applications in real database
c.execute("SELECT count(*), platform FROM job_applications GROUP BY platform")
print("Remaining applications by platform:", c.fetchall())

conn.close()
