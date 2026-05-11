import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import requests
from bs4 import BeautifulSoup
from multiprocessing import Pool, freeze_support
from html import unescape
from urllib.parse import urljoin, urlparse


# ============ DEFAULT CONFIG ============
DEFAULT_USERNAME = ""
DEFAULT_PASSWORD = ""
DEFAULT_OUTPUT_DIR = "/Users/willieliao/Downloads"
# ========================================


class SubmissionScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ManageBac Submission Scraper")
        self.root.geometry("700x700")
        
        self.cookies = None
        self.submissions = []
        self.student_vars = {}  # checkbox variables
        
        self.create_login_frame()
        self.create_student_frame()
        self.create_status_frame()
    
    def create_login_frame(self):
        """Create the login/URL input section."""
        frame = ttk.LabelFrame(self.root, text="Task Configuration", padding=10)
        frame.pack(fill="x", padx=10, pady=5)
        
        # Task URL
        ttk.Label(frame, text="Task URL:").grid(row=0, column=0, sticky="w", pady=2)
        self.url_entry = ttk.Entry(frame, width=70)
        self.url_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)
        
        # Username
        ttk.Label(frame, text="Username:").grid(row=1, column=0, sticky="w", pady=2)
        self.username_entry = ttk.Entry(frame, width=40)
        self.username_entry.insert(0, DEFAULT_USERNAME)
        self.username_entry.grid(row=1, column=1, sticky="ew", pady=2)
        
        # Password
        ttk.Label(frame, text="Password:").grid(row=2, column=0, sticky="w", pady=2)
        self.password_entry = ttk.Entry(frame, width=40, show="*")
        self.password_entry.insert(0, DEFAULT_PASSWORD)
        self.password_entry.grid(row=2, column=1, sticky="ew", pady=2)
        
        # Output directory
        ttk.Label(frame, text="Output Dir:").grid(row=3, column=0, sticky="w", pady=2)
        self.output_entry = ttk.Entry(frame, width=50)
        self.output_entry.insert(0, DEFAULT_OUTPUT_DIR)
        self.output_entry.grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Button(frame, text="Browse", command=self.browse_output).grid(row=3, column=2, padx=5)
        
        # Fetch button
        self.fetch_btn = ttk.Button(frame, text="Fetch Students", command=self.fetch_students)
        self.fetch_btn.grid(row=4, column=1, pady=10)
        
        frame.columnconfigure(1, weight=1)
    
    def create_student_frame(self):
        """Create the student selection section."""
        frame = ttk.LabelFrame(self.root, text="Select Students to Download", padding=10)
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Top row: Select all / none buttons + search box
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Select All", command=self.select_all).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Select None", command=self.select_none).pack(side="left", padx=5)
        
        # Search box on the right
        ttk.Label(btn_frame, text="Search:").pack(side="left", padx=(20, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.filter_students())
        self.search_entry = ttk.Entry(btn_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Clear", command=self.clear_search).pack(side="left", padx=5)
        
        # Scrollable student list
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self.student_list_frame = ttk.Frame(canvas)
        
        self.student_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.student_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        # Download button
        self.download_btn = ttk.Button(frame, text="Download Selected", command=self.download_selected, state="disabled")
        self.download_btn.pack(pady=10)
    
    def create_status_frame(self):
        """Create the status/log section."""
        frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        frame.pack(fill="x", padx=10, pady=5)
        
        self.status_label = ttk.Label(frame, text="Enter task URL and click 'Fetch Students'")
        self.status_label.pack()
        
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=5)
    
    def browse_output(self):
        """Open directory browser."""
        directory = filedialog.askdirectory()
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)
    
    def set_status(self, text):
        """Update status label."""
        self.status_label.config(text=text)
        self.root.update()
    
    def fetch_students(self):
        """Fetch student list from task URL."""
        task_url = self.url_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not task_url:
            messagebox.showerror("Error", "Please enter a task URL")
            return
        
        self.fetch_btn.config(state="disabled")
        self.progress.start()
        self.set_status("Logging in...")
        
        # Run in thread to keep GUI responsive
        thread = threading.Thread(target=self._fetch_students_thread, args=(task_url, username, password))
        thread.start()
    
    def _fetch_students_thread(self, task_url, username, password):
        """Background thread for fetching students."""
        try:
            # Extract school code from URL
            school_code = task_url.split('/')[2].split('.')[0]
            domain = task_url.split('/')[2].split('.', 1)[1]  # e.g., managebac.cn
            
            # Login
            self.cookies = self._login(school_code, domain, username, password)
            self.root.after(0, lambda: self.set_status("Fetching submissions..."))
            
            # Get submissions
            self.submissions = self._get_students_and_files(task_url, self.cookies)
            
            # Update GUI in main thread
            self.root.after(0, self._populate_student_list)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, lambda: self.set_status("Error occurred"))
        finally:
            self.root.after(0, lambda: self.fetch_btn.config(state="normal"))
            self.root.after(0, self.progress.stop)
    
    def _login(self, school_code, domain, email, password):
        """Login to ManageBac."""
        login_request = requests.get(f'https://{school_code}.{domain}/login')
        login_html = BeautifulSoup(login_request.text, features='lxml')
        csrf_token = login_html.find_all(
            name='meta', attrs={'name': 'csrf-token'}
        )[0].attrs['content']
        
        sessions_request = requests.post(
            f'https://{school_code}.{domain}/sessions',
            data={
                'authenticity_token': csrf_token,
                'login': email,
                'password': password,
                'commit': 'Sign-In'
            },
            cookies=login_request.cookies
        )
        return sessions_request.cookies
    
    def _get_students_and_files(self, task_url, cookies):
        """Get all students and their submission files."""
        response = requests.get(task_url, cookies=cookies)
        soup = BeautifulSoup(response.text, features='lxml')
        
        results_by_student = {}
        dropbox_section = soup.find('div', id='dropbox')
        if dropbox_section:
            tbody = dropbox_section.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                current_student = None
                current_files = []
                seen_file_ids = set()
                
                for row in rows:
                    student_link = row.select_one('td[rowspan] a[href*="student_id="]')
                    
                    if student_link:
                        if current_student and current_files:
                            results_by_student[current_student] = {
                                'student_name': current_student,
                                'files': current_files,
                                'criteria': [],
                                'comment': ''
                            }
                            current_files = []
                            seen_file_ids = set()
                        
                        current_student = student_link.get_text(strip=True)
                    
                    file_link = row.select_one('a[href*="s3.cn-north-1.amazonaws.com"][title]')
                    if file_link and current_student:
                        href = file_link.get('href', '')
                        filename = file_link.get('title', '')
                        
                        file_id_match = re.search(r'/file/(\d+)/', href)
                        file_id = file_id_match.group(1) if file_id_match else href
                        
                        if file_id not in seen_file_ids:
                            seen_file_ids.add(file_id)
                            current_files.append({
                                'name': filename,
                                'url': href
                            })
                
                if current_student and current_files:
                    results_by_student[current_student] = {
                        'student_name': current_student,
                        'files': current_files,
                        'criteria': [],
                        'comment': ''
                    }
        
        # Task pages contain submissions; gradebook pages contain criteria/comments.
        gradebook_soup = self._get_gradebook_task_soup(task_url, cookies, soup)
        if gradebook_soup:
            self._merge_gradebook_feedback(gradebook_soup, results_by_student)
        return list(results_by_student.values())

    def _get_gradebook_task_soup(self, task_url, cookies, task_soup):
        """Resolve and fetch matching gradebook task page from a task URL."""
        gradebook_url = self._find_gradebook_task_url(task_url, task_soup)
        if not gradebook_url:
            gradebook_url = self._find_gradebook_task_url_via_task_list(task_url, cookies)
        
        if not gradebook_url:
            return None
        
        try:
            response = requests.get(gradebook_url, cookies=cookies, timeout=60)
            response.raise_for_status()
        except Exception:
            return None
        
        return BeautifulSoup(response.text, features='lxml')

    def _find_gradebook_task_url(self, task_url, task_soup):
        """Find gradebook task URL directly from task page links."""
        for link in task_soup.select('a[href*="/gradebook/term/"][href*="/tasks/"]'):
            href = link.get('href', '').strip()
            if not href:
                continue
            return urljoin(task_url, href)
        return None

    def _find_gradebook_task_url_via_task_list(self, task_url, cookies):
        """Fallback: match task id against gradebook task list links."""
        class_match = re.search(r'/teacher/classes/(\d+)/', task_url)
        task_match = re.search(r'/tasks/(\d+)', task_url)
        if not class_match or not task_match:
            return None
        
        class_id = class_match.group(1)
        task_id = task_match.group(1)
        parsed = urlparse(task_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        task_list_url = f"{base_url}/teacher/classes/{class_id}/gradebook/tasks"
        
        try:
            response = requests.get(task_list_url, cookies=cookies, timeout=60)
            response.raise_for_status()
        except Exception:
            return None
        
        soup = BeautifulSoup(response.text, features='lxml')
        for link in soup.select('a[href*="/gradebook/term/"][href*="/tasks/"]'):
            href = link.get('href', '').strip()
            if not href:
                continue
            if re.search(rf'/tasks/{re.escape(task_id)}(?:\\b|$)', href):
                return urljoin(base_url, href)
        
        return None

    def _merge_gradebook_feedback(self, soup, results_by_student):
        """Merge criterion scores/comments from gradebook rows into results."""
        for row in soup.select('div.grid-table-row.student-grade'):
            student_link = row.select_one('a[href*="/teacher/users/"]')
            if not student_link:
                continue
            
            student_name = student_link.get_text(strip=True)
            if student_name not in results_by_student:
                continue
            
            criteria = []
            for criteria_section in row.select('div.criteria-grades'):
                label_tag = criteria_section.find('label')
                label = label_tag.get_text(strip=True) if label_tag else 'Criterion'
                
                selected = criteria_section.select_one('div.points-button.selected')
                score_text = selected.get_text(strip=True) if selected else ''
                
                if score_text:
                    criteria.append({
                        'name': label,
                        'score': score_text
                    })
            
            comment_text = ''
            comment_area = row.select_one('textarea[name="core_task[task_comment][comment]"]')
            if comment_area:
                comment_html = comment_area.get_text() or ''
                comment_text = self._html_to_text(comment_html)
            
            results_by_student[student_name]['criteria'] = criteria
            results_by_student[student_name]['comment'] = comment_text

    def _html_to_text(self, html_text):
        """Convert basic HTML string to readable plain text."""
        if not html_text:
            return ''
        
        fragment = BeautifulSoup(unescape(html_text), features='lxml')
        text = fragment.get_text('\n', strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def _populate_student_list(self):
        """Populate the student checkbox list."""
        # Clear existing
        for widget in self.student_list_frame.winfo_children():
            widget.destroy()
        self.student_vars.clear()
        
        if not self.submissions:
            ttk.Label(self.student_list_frame, text="No submissions found").pack()
            self.set_status("No submissions found")
            return
        
        # Create checkboxes for each student
        for i, sub in enumerate(self.submissions):
            var = tk.BooleanVar(value=True)
            self.student_vars[sub['student_name']] = var
            
            file_count = len(sub['files'])
            criteria = sub.get('criteria') or []
            comment = (sub.get('comment') or '').strip()
            
            parts = [f"{file_count} file{'s' if file_count != 1 else ''}"]
            if criteria:
                score_str = ', '.join(c['score'] for c in criteria)
                parts.append(f"score: {score_str}")
            parts.append(f"comment: {'TRUE' if comment else 'FALSE'}")
            
            text = f"{sub['student_name']} ({', '.join(parts)})"
            
            cb = ttk.Checkbutton(self.student_list_frame, text=text, variable=var)
            cb.pack(anchor="w", pady=2)
        
        self.download_btn.config(state="normal")
        total_files = sum(len(s['files']) for s in self.submissions)
        self.set_status(f"Found {len(self.submissions)} students with {total_files} files")
    
    def select_all(self):
        """Select all students."""
        for var in self.student_vars.values():
            var.set(True)
    
    def select_none(self):
        """Deselect all students."""
        for var in self.student_vars.values():
            var.set(False)
    
    def clear_search(self):
        """Clear the search box."""
        self.search_var.set("")
    
    def filter_students(self):
        """Filter student list based on search text."""
        search_text = self.search_var.get().lower()
        
        # Show/hide checkboxes based on search
        for widget in self.student_list_frame.winfo_children():
            if isinstance(widget, ttk.Checkbutton):
                student_text = widget.cget("text").lower()
                if search_text in student_text:
                    widget.pack(anchor="w", pady=2)
                else:
                    widget.pack_forget()
    
    def download_selected(self):
        """Download files for selected students."""
        selected = [name for name, var in self.student_vars.items() if var.get()]
        
        if not selected:
            messagebox.showwarning("Warning", "No students selected")
            return
        
        output_dir = self.output_entry.get().strip()
        if not output_dir:
            messagebox.showerror("Error", "Please specify output directory")
            return
        
        # Filter submissions to selected students
        selected_submissions = [s for s in self.submissions if s['student_name'] in selected]
        
        self.download_btn.config(state="disabled")
        self.progress.start()
        self.set_status("Downloading...")
        
        thread = threading.Thread(target=self._download_thread, args=(selected_submissions, output_dir))
        thread.start()
    
    def _download_thread(self, submissions, output_dir):
        """Background thread for downloading."""
        try:
            downloaded = 0
            skipped = 0
            failed = 0
            total = sum(len(s['files']) for s in submissions)
            
            for sub in submissions:
                student_folder = os.path.join(output_dir, self._get_valid_filename(sub['student_name']))
                
                for file_info in sub['files']:
                    filepath = os.path.join(student_folder, self._get_valid_filename(file_info['name']))
                    result = self._download_file(filepath, file_info['url'])
                    
                    if result == True:
                        downloaded += 1
                    elif result == 'skipped':
                        skipped += 1
                    else:
                        failed += 1
                    
                    self.root.after(0, lambda d=downloaded, s=skipped, f=failed, t=total: 
                        self.set_status(f"Progress: {d+s+f}/{t} (new: {d}, skipped: {s}, failed: {f})"))
                
                self._write_feedback_markdown(student_folder, sub)
            
            self.root.after(0, lambda: messagebox.showinfo("Complete", 
                f"Download complete!\n\nNew: {downloaded}\nSkipped: {skipped}\nFailed: {failed}"))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self.download_btn.config(state="normal"))
            self.root.after(0, self.progress.stop)
            self.root.after(0, lambda: self.set_status("Done"))
    
    def _get_valid_filename(self, s):
        """Convert string to valid filename."""
        s = str(s).strip().replace(' ', '_')
        return re.sub(r'(?u)[^-\w.]', '', s)
    
    def _download_file(self, filepath, url):
        """Download a single file."""
        if os.path.exists(filepath):
            return 'skipped'
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        try:
            response = requests.get(url, stream=True, timeout=120)
            response.raise_for_status()
            
            temp_filepath = filepath + '.tmp'
            with open(temp_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            os.rename(temp_filepath, filepath)
            return True
            
        except Exception:
            if os.path.exists(filepath + '.tmp'):
                os.remove(filepath + '.tmp')
            return False

    def _write_feedback_markdown(self, student_folder, submission):
        """Write criterion scores/comments to a markdown file per student."""
        criteria = submission.get('criteria') or []
        comment = (submission.get('comment') or '').strip()
        
        if not criteria and not comment:
            return
        
        os.makedirs(student_folder, exist_ok=True)
        md_path = os.path.join(student_folder, 'comment.md')
        
        lines = [
            f"# {submission['student_name']}",
            ""
        ]
        
        if criteria:
            lines.append("## Criteria")
            lines.append("")
            for c in criteria:
                lines.append(f"- {c['name']}: {c['score']}")
            lines.append("")
        
        if comment:
            lines.append("## Comment")
            lines.append("")
            lines.append(comment)
            lines.append("")
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines).rstrip() + '\n')


def main():
    freeze_support()
    root = tk.Tk()
    app = SubmissionScraperGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
