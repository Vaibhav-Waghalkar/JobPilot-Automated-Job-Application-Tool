import sqlite3

conn = sqlite3.connect('data/jobpilot.db')
c = conn.cursor()

applied = c.execute("SELECT count(*) FROM job_applications WHERE status = 'applied'").fetchone()[0]
print("Applied count:", applied)

falsely_skipped = c.execute("SELECT count(*) FROM job_applications WHERE status != 'applied' AND skip_reason LIKE '%Already applied%'").fetchone()[0]
print("Falsely skipped count:", falsely_skipped)

# Delete falsely marked entries
c.execute("DELETE FROM job_applications WHERE status != 'applied' AND skip_reason LIKE '%Already applied%'")
conn.commit()

remaining = c.execute("SELECT count(*) FROM job_applications").fetchone()[0]
print("Total job applications remaining:", remaining)

conn.close()
