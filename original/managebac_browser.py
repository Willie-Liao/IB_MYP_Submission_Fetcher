import re
import requests
from tqdm import tqdm
from bs4 import BeautifulSoup


def get_valid_filename(s):
    """
    Convert string to a valid filename.
    Remove leading/trailing spaces; convert spaces to underscores;
    remove anything that is not alphanumeric, dash, underscore, or dot.
    """
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)


def get_classes(school_code, jar, domain='managebac.com'):
    """
    Get list of classes for the logged-in student.
    
    Args:
        school_code: School code
        jar: Cookie jar from login
        domain: Domain suffix
    Returns:
        List of class dicts with 'name' and 'id' keys
    """
    student_request = requests.get(
        f'https://{school_code}.{domain}/student', cookies=jar)
    student_html = BeautifulSoup(student_request.text, features='lxml')
    classes_html = student_html.select(
        '#menu > ul > li[data-path^="classes"] > ul > li')
    classes = []
    for class_html in tqdm(classes_html, desc='Getting classes...'):
        if class_html.find('span') is None:
            continue
        classes.append({
            'name': class_html.find('span').text.strip(),
            'id': class_html.find('a').attrs['href'].split('/')[-1]
        })
    return classes


def get_files(school_code, jar, class_dict, domain='managebac.com'):
    """
    Get all files from a class's Files tab.
    
    Args:
        school_code: School code
        jar: Cookie jar from login
        class_dict: Dict with class 'id'
        domain: Domain suffix
    Returns:
        List of file dicts with 'name', 'url', 'author', 'date' keys
    """
    files = []
    files_htmls = get_files_htmls(
        jar,
        f'https://{school_code}.{domain}/student/classes/{class_dict["id"]}/files'
    )
    for files_html in tqdm(files_htmls, desc='Parsing...'):
        files += find_file_links(school_code, jar, files_html, domain=domain)
    return files


def get_files_htmls(jar, url):
    """Get all paginated HTML pages from a files URL."""
    htmls = []
    request = requests.get(url, cookies=jar)
    htmls.append(BeautifulSoup(request.text, features='lxml'))
    total_pages_html = htmls[0].select('ul.pagination li:nth-last-child(2) a')
    total_pages = int(total_pages_html[0].text) if len(total_pages_html) > 0 else 1
    current_page = 1
    while total_pages > current_page:
        request = requests.get(f'{url}/page/{str(current_page + 1)}', cookies=jar)
        htmls.append(BeautifulSoup(request.text, features='lxml'))
        current_page += 1
    return htmls


def find_file_links(school_code, jar, class_html, directory='', domain='managebac.com'):
    """Recursively find all file links in a class HTML page."""
    links = []
    files_html = class_html.find_all(class_='row file')
    for file_html in files_html:
        details = file_html.find(class_='details')
        if details is None:
            # is a folder
            foldername_html = file_html.find(class_='title').find('a')
            for page in tqdm(
                get_files_htmls(jar, f'https://{school_code}.{domain}{foldername_html["href"]}'),
                desc=f'Parsing {foldername_html.text.strip()}...'
            ):
                links += find_file_links(
                    school_code, jar, page,
                    directory=directory + get_valid_filename(foldername_html.text.strip()) + '/',
                    domain=domain
                )
        else:
            filename_html = details.find('a')
            author = details.find('label').text.replace('\nby\n', '').strip()
            creation_date = file_html.find_all(class_='hidden-xs')[-1].text
            links.append({
                'type': 'file',
                'name': directory + filename_html.text,
                'author': author,
                'date': creation_date,
                'url': filename_html['href']
            })
    return links


def get_students_and_files(task_url, cookies):
    """
    Get all students and their submission files from a task page (teacher view).
    
    Args:
        task_url: Full URL to the task page
        cookies: Cookie jar from login
    Returns:
        List of dicts with 'student_name' and 'files' keys
    """
    response = requests.get(task_url, cookies=cookies)
    soup = BeautifulSoup(response.text, features='lxml')
    
    # Save for debugging
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    
    results = []
    
    # Find the dropbox table
    dropbox_section = soup.find('div', id='dropbox')
    if not dropbox_section:
        tqdm.write("Could not find dropbox section")
        return []
    
    tbody = dropbox_section.find('tbody')
    if not tbody:
        tqdm.write("Could not find tbody")
        return []
    
    rows = tbody.find_all('tr')
    tqdm.write(f'Found {len(rows)} table rows')
    
    current_student = None
    current_files = []
    seen_file_ids = set()
    
    for row in rows:
        # Check if this row starts a new student
        student_link = row.select_one('td[rowspan] a[href*="student_id="]')
        
        if student_link:
            # Save previous student's files
            if current_student and current_files:
                results.append({
                    'student_name': current_student,
                    'files': current_files
                })
                current_files = []
                seen_file_ids = set()
            
            current_student = student_link.get_text(strip=True)
            tqdm.write(f'Found student: {current_student}')
        
        # Get file from this row
        file_link = row.select_one('a[href*="s3.cn-north-1.amazonaws.com"][title]')
        if file_link and current_student:
            href = file_link.get('href', '')
            filename = file_link.get('title', '')
            
            # Deduplicate by file ID
            file_id_match = re.search(r'/file/(\d+)/', href)
            file_id = file_id_match.group(1) if file_id_match else href
            
            if file_id not in seen_file_ids:
                seen_file_ids.add(file_id)
                current_files.append({
                    'name': filename,
                    'url': href
                })
    
    # Don't forget the last student
    if current_student and current_files:
        results.append({
            'student_name': current_student,
            'files': current_files
        })
    
    total_files = sum(len(s['files']) for s in results)
    tqdm.write(f'Parsed {len(results)} students with {total_files} total files')
    
    return results
