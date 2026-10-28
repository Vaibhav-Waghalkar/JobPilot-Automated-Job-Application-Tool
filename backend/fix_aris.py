import sqlite3

conn = sqlite3.connect('data/jobpilot.db')
c = conn.cursor()
c.execute("UPDATE project_tier_items SET has_tests = 0 WHERE project_name = 'ARIS-AI_Assistant'")
conn.commit()
print("ARIS items:", c.execute("SELECT project_name, tier, has_tests, has_docker, parent_project FROM project_tier_items WHERE project_name LIKE 'ARIS%'").fetchall())
conn.close()
