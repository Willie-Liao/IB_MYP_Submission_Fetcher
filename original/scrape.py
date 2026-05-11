import argparse
import managebac_authenticator
import managebac_browser
import downloader
from tqdm import tqdm
from multiprocessing import Pool, freeze_support

if __name__ == '__main__':
    freeze_support()

    parser = argparse.ArgumentParser(
        description='Download all the files in the \'Files\' tab for ManageBac classes.'
    )
    parser.add_argument('school_code', help='https://<school_code>.managebac.com')
    parser.add_argument('username', help='Login email address')
    parser.add_argument('password', help='Login password')
    parser.add_argument('output_dir', help='Output directory location')
    parser.add_argument('class_name', help='Name of the class to filter', nargs='?')
    parser.add_argument('--domain', default='managebac.com', 
                        help='Domain suffix (default: managebac.com, use managebac.cn for China)')

    args = parser.parse_args()

    cookie_jar = managebac_authenticator.get_jar(
        args.school_code, args.username, args.password, domain=args.domain
    )
    classes = managebac_browser.get_classes(args.school_code, cookie_jar, domain=args.domain)

    if args.class_name is not None:
        classes = [c for c in classes if c['name'] == args.class_name]
    
    dest_dir = args.output_dir
    if not dest_dir.endswith('/') and not dest_dir.endswith('\\'):
        dest_dir += '/'

    job_pool = Pool()

    with tqdm(desc='Class Progress', postfix='') as t:
        for class_dict in classes:
            t.postfix = class_dict['name']
            files = managebac_browser.get_files(
                args.school_code, cookie_jar, class_dict, domain=args.domain
            )
            downloader.download(
                files, 
                job_pool=job_pool, 
                dir=dest_dir + managebac_browser.get_valid_filename(class_dict['name'])
            )
            t.update()

    managebac_authenticator.logout(args.school_code, cookie_jar, domain=args.domain)

