import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
import re
import json
import time
import os
import unicodedata
from PIL import Image, ImageDraw, ImageFont
import os
from collections import Counter
from IPython.display import display as Display

class bw:
    def __init__(self, url, except_titles=['購入特典', '合本版']):
        self.except_titles = except_titles
        self.author_url = url

        self.s = requests.Session()
        adapter = HTTPAdapter(max_retries=5)
        self.s.mount('http://', adapter)
        self.s.mount('https://', adapter)
        response = self.s.get(self.author_url)
        self.soup = BeautifulSoup(response.content, 'html.parser')

        script_tags = self.soup.find('script', attrs={'type': 'application/ld+json'})
        author_name = json.loads(script_tags.text)['itemListElement'][1]['item']['name']

        self.author_name_orig = author_name
        self.author_name = unicodedata.normalize('NFKC', author_name).replace(' ', '')
        print(author_name)
        
        os.makedirs('books_json', exist_ok=True)
        os.makedirs('covers', exist_ok=True)
        os.makedirs('merge_covers', exist_ok=True)
        

    def get_books_from_author(self):
        os.makedirs(f'books_json/{self.author_name}', exist_ok=True)
        all_books = []
        # response = s.get(self.url)
        # soup = BeautifulSoup(response.content, 'html.parser')

        li_tags = self.soup.find_all('li', class_='m-tile')

        # 输出结果
        for li in li_tags:
            findp = li.find('p', class_='m-book-item__title')
            if any(except_title in findp.text for except_title in self.except_titles):
                print('Skip', findp.text.strip())
                continue
            else:
                href = findp.find('a')['href']
                if 'series' in href:
                    books = self.get_books_from_list(href)
                    all_books.extend(books)
                else:
                    book = self.get_cover_url_from_book(href)
                    all_books.append(book)
        time.sleep(1)
        all_books = sorted(all_books, key=lambda x: x['date'])
        with open(f'books_json/{self.author_name}/all_books.json', 'w', encoding='utf-8') as f:
            json.dump(all_books, f, ensure_ascii=False, indent=4)
        self.all_books = all_books
        return all_books

    def get_full_size_cover_url(self, url):
        if "rimg.bookwalker.jp" in url:
            url = re.sub(
                r":\/\/[^/]*\/([0-9]+)\/[0-9a-zA-Z_]+(\.[^/.]*)$",
                r"://c.bookwalker.jp/\1/t_700x780\2",
                url,
            )

        if "c.bookwalker.jp" in url:
            match = re.search(r":\/\/[^/]*\/([0-9]+)\/[^/]*(?:[?#].*)?$", url)
            if match:
                number = match[1]
                reversed_number = int(number[::-1]) - 1
                url = (
                    "https://c.bookwalker.jp/coverImage_"
                    + str(reversed_number)
                    + re.sub(r".*(\.[^/.?#]*)(?:[?#].*)?$", r"\1", url)
                )

        return url

    def get_cover_url_from_book(self, url):
        response = self.s.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        # cover url
        try:
            cover_url = soup.find('img', class_='lazy')['data-original']
        except:
            cover_url = ''
        
        # title
        # title = soup.find('h1', class_="p-main__title").text
            
        # pages
        try:
            pagetag = soup.find('dt', string='ページ概数')
            pages = pagetag.find_next_sibling('dd').text
            # print(pages)
        except:
            pages = ''
        
        # publication date
        try:
            datetag = soup.find('dt', string='底本発行日')
            date = datetag.find_next_sibling('dd').text
            y, m, d = date.split('/')
            date = f'{y}-{int(m):02d}-{int(d):02d}'
            # print(date)
        except:
            # try:
            #     y, m = date.split('/')
            #     date = f'{y}-{int(m):02d}'
            # except:
            date = ''

        # illustrator
        try:
            itag = soup.find('dt', string='イラスト')
            illustrator = itag.find_next_sibling('dd').text.replace('\n', '')
            # print(illustrator)
        except:
            illustrator = ''
            
        # author
        author = ''
        for s in ['著者', '著', '作者', '作画', '漫画', '編']:
            try:
                atag = soup.find('dt', string=s)
                author = atag.find_next_sibling('dd').text
                author = author.strip()
                author = re.sub('\n+', ',', author)
                break
            except:
                continue

        if author != self.author_name_orig:
            tag = 'not_novel'
        else:
            tag = 'novel'
        
        if author in [f'{self.author_name_orig}(著)', f'{self.author_name_orig}(著者)', f'{self.author_name_orig}（著）', f'{self.author_name_orig}（著者）', f'{self.author_name}(著)', f'{self.author_name}(著者)', f'{self.author_name}（著）', f'{self.author_name}（著者）']:
            author = self.author_name_orig

        # info dict
        script = soup.find('script', string=re.compile('item_brand'))
        pattern = re.compile(r'window.bwDataLayer.push\((.*?)\);', re.DOTALL)
        if script:
            match = pattern.search(script.string)
        else:
            match = None
        
        if match:
            save_dic = {}
            data = json.loads(match.group(1))
            items = data['ecommerce']['items'][0]
            save_dic = {
                'title': items['item_name'],
                'date': date,
                'author': author,
                'illustrator': illustrator,
                'publisher': items['item_publisher'],
                'brand': items['item_brand'],
                'pages': pages,
                'category': items['item_category'],
                'series': items['item_series'],
                'price': {'total': items['price'], 'tax': items['tax'], 'currency': items['currency']},
                'cover': cover_url,
                'full_size_cover': self.get_full_size_cover_url(cover_url),
                'bw_url': url,
                'online_date': items['item_date'],
                'tag': tag
            }
            print(save_dic)
            return save_dic
        else:
            print(f'No match for book {url}')
            err_dic = {
                'bw_url': url
            }
            return err_dic
            
    def get_books_from_list(self, url):
        all_books = []
        response = self.s.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        li_tags = soup.find_all('li', class_='m-tile')

        # 输出结果
        for li in li_tags:
            # m = li.find()
            href = li.find('p', class_='m-book-item__title').find('a')['href']
            if 'series' in href:
                raise Exception(f'Series in series! {url}')
            else:
                dic = self.get_cover_url_from_book(href)
                if any(except_title in dic['title'] for except_title in self.except_titles):
                    continue
                all_books.append(dic)
            time.sleep(1)

        return all_books


    def format_json(self, read_saved_json=False, path=None):
        if not read_saved_json:
            books_to_be_edited = self.all_books
        else:
            if not path:
                path = f'books_json/{self.author_name}/all_books.json'
            with open(path, 'r', encoding='utf-8') as f:
                books_to_be_edited = json.load(f)
                print('json file loaded.')
    
        books_to_be_edited = [i for i in books_to_be_edited if '合本版' not in i['title']]

        # books_online = []
        books_manga = []
        books_novel = []
        books_other = []
        books_artbook = []

        print('Online date only:')
        for i in books_to_be_edited:
            i['illustrator'] = unicodedata.normalize('NFKC', i['illustrator'])

            if i['category'] == 'マンガ':
                i['tag'] = 'manga'
            elif i['category'] == '画集':
                i['tag'] = 'artbook'
            elif i['category'] in ['ライトノベル', '新文芸', '文芸・小説', '新書']:
                i['tag'] = 'novel'
            else:
                i['tag'] = 'other'

            # if not i['author'].startswith(self.author_name):
            if i['tag'] == 'novel' and self.author_name_orig != i['author']:
                i['tag'] = i['tag'] + '_multi' # Mutiple authors
                
            if i['date'] == '':
                print(i)
                i['date'] = i['online_date']
                i['tag'] = i['tag']+'_online' # No physical publication date


            if 'manga' in i['tag']:
                books_manga.append(i)
            elif 'novel' in i['tag']:
                books_novel.append(i)
            elif 'other' in i['tag']:
                books_other.append(i)
            elif 'artbook' in i['tag']:
                books_artbook.append(i)
        
        all_kinds = {'manga': books_manga, 'novel': books_novel, 'other': books_other, 'artbook': books_artbook}
        new_all_books = []
        
        for k, v in all_kinds.items():
            if len(v) < 1:
                continue
            v = sorted(v, key=lambda x: x['date'])
            with open(f'books_json/{self.author_name}/{k}.json', 'w', encoding='utf-8') as f:
                json.dump(v, f, ensure_ascii=False, indent=4)
            new_all_books.extend(v)
            
        # new_all_books = books_online + books_manga + books_novel + books_other
        new_all_books = sorted(new_all_books, key=lambda x: x['date'])
        with open(f'books_json/{self.author_name}/format_books.json', 'w', encoding='utf-8') as f:
            json.dump(new_all_books, f, ensure_ascii=False, indent=4)
        self.formatted_books = new_all_books
        return new_all_books


    def download_covers(self, read_saved_json=False, path=None):
        os.makedirs(f'covers/{self.author_name}', exist_ok=True)
        if not read_saved_json:
            pass
        else:
            if not path:
                path = f'books_json/{self.author_name}/format_books.json'
            self.formatted_books = json.load(open(path, 'r', encoding='utf-8'))
            print(f'Read json from {path}')

        for i in self.formatted_books:
            url = i.get('full_size_cover', i.get('cover'))
            if not url:
                print(f'{i["title"]} no cover url!')
                continue
            
            os.makedirs(f'covers/{self.author_name}/{i["tag"]}', exist_ok=True)
            
            if '/' in i['title']:
                title = i['title'].replace('/', '／')
            else:
                title = i['title']
                
            filename = 'covers/{}/{}/{}-{}.jpg'.format(self.author_name, i['tag'], i['date'], title)
            # check if file exist
            if os.path.isfile(filename):
                print(f'{filename} exists!')
                continue
            response = self.s.get(i['full_size_cover'])
            try:                    
                if 'AccessDenied' in response.content.decode():
                    response = self.s.get(i['cover'])
                    print('Access Denied! Use low-res cover.')
                    try:
                        if 'AccessDenied' in response.content.decode():
                            continue 
                    except:
                        pass
            except:
                pass
            with open(filename, 'wb') as f:
                f.write(response.content)
                print(f'{filename} saved!')
                time.sleep(1)
                

    def merge_covers(self, h=500, n_col=5, covers_tag = ['novel', 'novel_online'], covers_dir=None, fontpath='~/.fonts/SourceHanSansCN-Regular.otf', year_color=None, display=False):
        os.makedirs(f'merge_covers/{self.author_name}', exist_ok=True)

        covers = []
        
        if covers_dir:
            tag = 'sp'
            for dir in covers_dir:
                try:
                    img_list = os.listdir(dir)
                except:
                    continue
                img_list = [f"{dir}/{i}" for i in img_list]
                img_list = [i for i in img_list if i.endswith('.jpg') or i.endswith('.png')]
                covers.extend(img_list)
        else:
            tag = '-'.join(covers_tag)
            for i in covers_tag:
                dir = f'covers/{self.author_name}/{i}/'
                try:
                    img_list = os.listdir(dir)
                except:
                    continue
                img_list = [dir+i for i in img_list]
                img_list = [i for i in img_list if i.endswith('.jpg') or i.endswith('.png')]
                covers.extend(img_list)
        covers = sorted(covers, key=lambda x: x.split('/')[-1])

        min_w = None
        resized_images = []
        for cover in covers:
            img = Image.open(os.path.join(cover))
            w = int(img.width * h / img.height)
            img = img.resize((w, h))
            if min_w is None or w < min_w:
                min_w = w
            resized_images.append(img)

        cols = []
        for i in range(0, len(resized_images), n_col):
            col = Image.new('RGB', (min_w * min(n_col, len(resized_images) - i), h))
            for j in range(min(n_col, len(resized_images) - i)):
                img = resized_images[i + j].crop((0, 0, min_w, h))
                col.paste(img, (j * min_w, 0))
            cols.append(col)

        final_img = Image.new('RGB', (min_w * n_col, h * len(cols)), color='white')
        for i, col in enumerate(cols):
            final_img.paste(col, (0, i * h))

        # show img
        # display(final_img)
        final_img.save(f'merge_covers/{self.author_name}/covers_h{h}_col{n_col}_{tag}.png')
        print(f'merge_covers/{self.author_name}/covers_h{h}_col{n_col}_{tag}.png saved!')
        if display:
            Display(final_img)
        
        # Merge covers with year
        if not year_color:
            year_color = {
                '2000': (236, 171, 231),
                '2001': (34, 189, 96),
                '2002': (152, 184, 165),
                '2003': (41, 81, 25),
                '2004': (204, 120, 34),
                '2005': (95, 17, 46),
                '2006': (251, 233, 112),
                '2007': (79, 69, 153),
                '2008': (142, 223, 52),
                '2009': (58, 4, 209),
                '2010': (214, 40, 47),
                '2011': (99, 104, 88),
                '2012': (221, 216, 44),
                '2013': (96, 219, 229),
                '2014': (190, 157, 118),
                '2015': (86, 195, 218),
                '2016': (250, 189, 12),
                '2017': (125, 253, 16),
                '2018': (229, 89, 25),
                '2019': (51, 60, 231),
                '2020': (197, 37, 188),
                '2021': (178, 164, 205),
                '2022': (29, 193, 210),
                '2023': (70, 193, 79),
                '2024': (194, 119, 53),
                '2025': (18, 215, 212),
                '2026': (156, 81, 19),
                '2027': (239, 42, 180),
                '2028': (97, 133, 108),
                '2029': (148, 2, 146),
                '2030': (17, 139, 44),
                '2031': (198, 170, 108),
                '2032': (17, 30, 195),
                '2033': (87, 156, 57),
                '2034': (197, 6, 9),
                '2035': (85, 205, 186),
                '2036': (29, 87, 228),
                '2037': (218, 124, 193),
                '2038': (95, 101, 40),
                '2039': (77, 60, 190),
                '2040': (247, 149, 142)
        }

        years = [name.split('/')[-1][:4] for name in covers]
        year_n = dict(Counter(years))
        
        barwidth = h - int(h/100*87)

        # min_w = None
        # resized_images = []
        # for cover in covers:
        #     img = Image.open(cover)
        #     w = int(img.width * h / img.height)
        #     img = img.resize((w, h))
        #     if min_w is None or w < min_w:
        #         min_w = w
        #     resized_images.append(img)

        # cols = []
        # for i in range(0, len(resized_images), n_col):
        #     col = Image.new('RGB', (min_w * min(n_col, len(resized_images) - i), h))
        #     for j in range(min(n_col, len(resized_images) - i)):
        #         img = resized_images[i + j].crop((0, 0, min_w, h))
        #         col.paste(img, (j * min_w, 0))
        #     cols.append(col)

        new_img = Image.new('RGB', (min_w * n_col, (h+barwidth) * len(cols)), color='white')
        for i, col in enumerate(cols):
            new_img.paste(col, (0, i * (h+barwidth)))

        # new_img = final_img.copy()
        draw = ImageDraw.Draw(new_img)
        # font = ImageFont.load_default()
        font = ImageFont.truetype(fontpath, int(h/10))

        previous_year = None
        for i, cover in enumerate(covers):
            year = cover.split('/')[-1][:4]
            color = year_color.get(year, (255, 255, 255))  # 如果年份不在映射中，使用黑色
            # anti_color = tuple([255 - c for c in color])  # 反色
            x = (i % n_col) * min_w
            y = (i // n_col) * h
            draw.rectangle([(x, y + h + i//n_col * barwidth), (x + min_w, y + h + (i//n_col+1) * barwidth)], outline=color, fill=color)
            # draw.line([(x, y + int(h/10*9)), (x + min_w, y + int(h/10*9))], fill=color, width=int(h/8))
            if year != previous_year:
                draw.text((x + int(h/20), y + int(h/100*85) + (i//n_col+1) * barwidth), f'{year} ({year_n[year]}本)', fill='white', font=font, stroke_width=int(h/100), stroke_fill='black')
            previous_year = year
        # display(new_img)
        new_img.save(f'merge_covers/{self.author_name}/covers_h{h}_col{n_col}_{tag}_years.png')
        print(f'merge_covers/{self.author_name}/covers_h{h}_col{n_col}_{tag}_years.png saved')
        if display:
            Display(new_img)
        
        
    def merge_covers_w(self, w=200, n_col=5, covers_tag = ['novel', 'novel_online'], covers_dir=None, fontpath='~/.fonts/SourceHanSansCN-Regular.otf', year_color=None, display=False):
        os.makedirs(f'merge_covers/{self.author_name}', exist_ok=True)

        covers = []
        
        if covers_dir:
            tag = 'sp'
            for dir in covers_dir:
                try:
                    img_list = os.listdir(dir)
                except:
                    continue
                img_list = [f"{dir}/{i}" for i in img_list]
                img_list = [i for i in img_list if i.endswith('.jpg') or i.endswith('.png')]
                covers.extend(img_list)
        else:
            tag = '-'.join(covers_tag)
            for i in covers_tag:
                dir = f'covers/{self.author_name}/{i}/'
                try:
                    img_list = os.listdir(dir)
                except:
                    continue
                img_list = [dir+i for i in img_list]
                img_list = [i for i in img_list if i.endswith('.jpg') or i.endswith('.png')]
                covers.extend(img_list)
        covers = sorted(covers, key=lambda x: x.split('/')[-1])

        min_h = None
        resized_images = []
        for cover in covers:
            img = Image.open(os.path.join(cover))
            h = int(img.height * w / img.width)
            img = img.resize((w, h))
            if min_h is None or h < min_h:
                min_h = h
            resized_images.append(img)

        cols = []
        for i in range(0, len(resized_images), n_col):
            col = Image.new('RGB', (w * min(n_col, len(resized_images) - i), min_h))
            for j in range(min(n_col, len(resized_images) - i)):
                img = resized_images[i + j].crop((0, 0, w, min_h))
                col.paste(img, (j * w, 0))
            cols.append(col)

        final_img = Image.new('RGB', (w * n_col, min_h * len(cols)), color='white')
        for i, col in enumerate(cols):
            final_img.paste(col, (0, i * min_h))

        # show img
        # display(final_img)
        final_img.save(f'merge_covers/{self.author_name}/covers_w{w}_col{n_col}_{tag}.png')
        print(f'merge_covers/{self.author_name}/covers_w{w}_col{n_col}_{tag}.png saved!')
        if display:
            Display(final_img)
        
        # Merge covers with year
        if not year_color:
            year_color = {
                '2000': (236, 171, 231),
                '2001': (34, 189, 96),
                '2002': (152, 184, 165),
                '2003': (41, 81, 25),
                '2004': (204, 120, 34),
                '2005': (95, 17, 46),
                '2006': (251, 233, 112),
                '2007': (79, 69, 153),
                '2008': (142, 223, 52),
                '2009': (58, 4, 209),
                '2010': (214, 40, 47),
                '2011': (99, 104, 88),
                '2012': (221, 216, 44),
                '2013': (96, 219, 229),
                '2014': (190, 157, 118),
                '2015': (86, 195, 218),
                '2016': (250, 189, 12),
                '2017': (125, 253, 16),
                '2018': (229, 89, 25),
                '2019': (51, 60, 231),
                '2020': (197, 37, 188),
                '2021': (178, 164, 205),
                '2022': (29, 193, 210),
                '2023': (70, 193, 79),
                '2024': (194, 119, 53),
                '2025': (18, 215, 212),
                '2026': (156, 81, 19),
                '2027': (239, 42, 180),
                '2028': (97, 133, 108),
                '2029': (148, 2, 146),
                '2030': (17, 139, 44),
                '2031': (198, 170, 108),
                '2032': (17, 30, 195),
                '2033': (87, 156, 57),
                '2034': (197, 6, 9),
                '2035': (85, 205, 186),
                '2036': (29, 87, 228),
                '2037': (218, 124, 193),
                '2038': (95, 101, 40),
                '2039': (77, 60, 190),
                '2040': (247, 149, 142)
        }

        years = [name.split('/')[-1][:4] for name in covers]
        year_n = dict(Counter(years))
        
        barwidth = min_h - int(min_h/100*87)

        # min_w = None
        # resized_images = []
        # for cover in covers:
        #     img = Image.open(cover)
        #     w = int(img.width * min_h / img.height)
        #     img = img.resize((w, min_h))
        #     if min_w is None or w < min_w:
        #         min_w = w
        #     resized_images.append(img)

        # cols = []
        # for i in range(0, len(resized_images), n_col):
        #     col = Image.new('RGB', (w * min(n_col, len(resized_images) - i), min_h))
        #     for j in range(min(n_col, len(resized_images) - i)):
        #         img = resized_images[i + j].crop((0, 0, w, min_h))
        #         col.paste(img, (j * w, 0))
        #     cols.append(col)

        new_img = Image.new('RGB', (w * n_col, (min_h+barwidth) * len(cols)), color='white')
        for i, col in enumerate(cols):
            new_img.paste(col, (0, i * (min_h+barwidth)))

        # new_img = final_img.copy()
        draw = ImageDraw.Draw(new_img)
        # font = ImageFont.load_default()
        font = ImageFont.truetype(fontpath, int(min_h/10))

        previous_year = None
        for i, cover in enumerate(covers):
            year = cover.split('/')[-1][:4]
            color = year_color.get(year, (255, 255, 255))  # 如果年份不在映射中，使用黑色
            # anti_color = tuple([255 - c for c in color])  # 反色
            x = (i % n_col) * w
            y = (i // n_col) * min_h
            draw.rectangle([(x, y + min_h + i//n_col * barwidth), (x + w, y + min_h + (i//n_col+1) * barwidth)], outline=color, fill=color)
            # draw.line([(x, y + int(h/10*9)), (x + min_w, y + int(h/10*9))], fill=color, width=int(h/8))
            if year != previous_year:
                draw.text((x + int(min_h/20), y + int(min_h/100*85) + (i//n_col+1) * barwidth), f'{year} ({year_n[year]}本)', fill='white', font=font, stroke_width=int(min_h/100), stroke_fill='black')
            previous_year = year
        # display(new_img)
        new_img.save(f'merge_covers/{self.author_name}/covers_w{w}_col{n_col}_{tag}_years.png')
        print(f'merge_covers/{self.author_name}/covers_w{w}_col{n_col}_{tag}_years.png saved')
        if display:
            Display(new_img)