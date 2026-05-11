import requests
from tqdm import tqdm
from bs4 import BeautifulSoup


def get_jar(school_code, email, password, domain='managebac.com'):
    """
    Get the cookie jar for further MB requests by logging in.

    Args:
        school_code: The part between https:// and .managebac.com/cn
        email: Login email address
        password: Login password
        domain: Domain suffix (default: managebac.com, use managebac.cn for China)
    Returns:
        A Requests cookie jar to be used for further requests
    """
    tqdm.write('Logging in...')
    
    # Get login page and CSRF token
    login_request = requests.get(f'https://{school_code}.{domain}/login')
    login_html = BeautifulSoup(login_request.text, features='lxml')
    csrf_token = login_html.find_all(
        name='meta', attrs={'name': 'csrf-token'}
    )[0].attrs['content']

    # Submit login
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
    
    tqdm.write('Logged in.')
    return sessions_request.cookies


def logout(school_code, jar, domain='managebac.com'):
    """
    Log out of the session.

    Args:
        school_code: The part between https:// and .managebac.com/cn
        jar: Cookie jar containing login information
        domain: Domain suffix (default: managebac.com)
    Returns:
        True if successful, False if not
    """
    logout_request = requests.get(
        f'https://{school_code}.{domain}/logout', cookies=jar)
    return logout_request.status_code == 200
