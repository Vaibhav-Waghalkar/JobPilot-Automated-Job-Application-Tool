from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse

mock_app = FastAPI(title="JobPilot Local Mock Form")

HTML_PAGE_1 = """
<!DOCTYPE html>
<html>
<head><title>Job Application - Step 1 Personal Info</title></head>
<body style="font-family:sans-serif; max-width:600px; margin:40px auto; padding:20px; border:1px solid #ccc;">
  <h2>Step 1 of 3: Personal Information</h2>
  <form action="/mock/step2" method="POST">
    <div style="margin-bottom:12px;">
      <label for="name">Full Name</label><br/>
      <input type="text" id="name" name="name" style="width:100%; padding:8px;" required />
    </div>
    <div style="margin-bottom:12px;">
      <label for="email">Email Address</label><br/>
      <input type="email" id="email" name="email" style="width:100%; padding:8px;" required />
    </div>
    <div style="margin-bottom:12px;">
      <label for="phone">Phone Number</label><br/>
      <input type="text" id="phone" name="phone" style="width:100%; padding:8px;" required />
    </div>
    <button type="submit" style="padding:8px 16px;">Next</button>
  </form>
</body>
</html>
"""

HTML_PAGE_2 = """
<!DOCTYPE html>
<html>
<head><title>Job Application - Step 2 Technical & Files</title></head>
<body style="font-family:sans-serif; max-width:600px; margin:40px auto; padding:20px; border:1px solid #ccc;">
  <h2>Step 2 of 3: Technical Experience & Resume</h2>
  <form action="/mock/step3" method="POST" enctype="multipart/form-data">
    <div style="margin-bottom:12px;">
      <label for="role">Target Role</label><br/>
      <select id="role" name="role" style="width:100%; padding:8px;">
        <option value="Backend">Backend</option>
        <option value="Full Stack">Full Stack</option>
        <option value="Python">Python</option>
      </select>
    </div>
    <div style="margin-bottom:12px;">
      <label for="resume">Upload Resume</label><br/>
      <input type="file" id="resume" name="resume" style="width:100%;" />
    </div>
    <div style="margin-bottom:12px;">
      <label for="unknown_q">What is your favorite distributed consensus algorithm?</label><br/>
      <input type="text" id="unknown_q" name="unknown_q" style="width:100%; padding:8px;" />
    </div>
    <button type="submit" style="padding:8px 16px;">Continue</button>
  </form>
</body>
</html>
"""

HTML_PAGE_3 = """
<!DOCTYPE html>
<html>
<head><title>Job Application - Step 3 Review & Submit</title></head>
<body style="font-family:sans-serif; max-width:600px; margin:40px auto; padding:20px; border:1px solid #ccc;">
  <h2>Step 3 of 3: Review & Final Submission</h2>
  <form action="/mock/submit" method="POST">
    <p>Please review your details. Click Submit Application to complete.</p>
    <div style="margin-bottom:12px;">
      <label><input type="checkbox" name="agree" value="yes" checked /> I certify the details provided are accurate.</label>
    </div>
    <button type="submit" style="padding:8px 16px; background:#10b981; color:#fff; border:none;">Submit</button>
  </form>
</body>
</html>
"""

HTML_SUCCESS = """
<!DOCTYPE html>
<html>
<head><title>Application Submitted</title></head>
<body style="font-family:sans-serif; max-width:600px; margin:40px auto; padding:20px; text-align:center;">
  <h2 style="color:#10b981;">Application Successfully Submitted!</h2>
  <p>Thank you for applying. We will review your profile.</p>
</body>
</html>
"""

@mock_app.get("/mock/apply", response_class=HTMLResponse)
async def mock_apply():
    return HTML_PAGE_1

@mock_app.post("/mock/step2", response_class=HTMLResponse)
async def mock_step2():
    return HTML_PAGE_2

@mock_app.post("/mock/step3", response_class=HTMLResponse)
async def mock_step3():
    return HTML_PAGE_3

@mock_app.post("/mock/submit", response_class=HTMLResponse)
async def mock_submit():
    return HTML_SUCCESS
