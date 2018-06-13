from datetime import date
from bs4 import BeautifulSoup
import requests
import re
import unicodedata

# My personal keys for testing the API
try:
    import testkeys
except ImportError:
    pass # super dumb but i need it for debugging atm

class AuthFailure(Exception):
    """In case API authentication fails"""
    pass


class SchoolSoft(object):
    """SchoolSoft Core API (Unofficial)"""

    def __init__(self, school, username, password, usertype = 1):
        """
        school = School being accessed
        username = Username of account being logged in
        password = Password of account being logged in
        usertype = Type of account;
        0 = teacher, 1 = student
        """
        self.school = school

        self.username = username
        self.password = password
        self.usertype = usertype

        self.cookies = {}

        _login_page_re = r"https://sms(\d*).schoolsoft.se/%s/html/redirect_login.htm"
        self._login_page_re = re.compile(_login_page_re % school)

        # Might not be needed, still gonna leave it here
        self.login_page = "https://sms5.schoolsoft.se/{}/jsp/Login.jsp".format(school)

    def try_get(self, url, attempts = 0):
        """
        Tries to get URL info using
        self.username && self.password

        Mainly for internal calling;
        however can be used to fetch from pages not yet added to API.
        """
        r = requests.get(url, cookies=self.cookies)

        login_page_match = self._login_page_re.match(r.url)
        if login_page_match:
            server_n = login_page_match.groups()
            if attempts < 1:
                # Sends a post request with self.username && self.password
                loginr = requests.post(self.login_page, data = {
                    "action": "login",
                    "usertype": self.usertype,
                    "ssusername": self.username,
                    "sspassword": self.password
                    }, cookies=self.cookies, allow_redirects=False)

                # Saves login cookie for faster access after first call
                self.cookies = loginr.cookies

                return self.try_get(url, attempts+1)
            else:
                raise AuthFailure("Invalid username or password")
        else:
            return r

    def fetch_lunch_menu(self):
        """
        Fetches the lunch menu for the entire week
        Returns an ordered list with days going from index 0-4
        This list contains all the food on that day
        """
        menu_html = self.try_get("https://sms5.schoolsoft.se/{}/jsp/student/right_student_lunchmenu.jsp?menu=lunchmenu".format(self.school))
        menu = BeautifulSoup(menu_html.text, "html.parser")

        lunch_menu = []

        for div in menu.find_all("td", {"style": "word-wrap: break-word"}):
            food_info = div.get_text(separator=u"<br/>").split(u"<br/>")
            lunch_menu.append(food_info)

        return lunch_menu

    def fetch_schedule(self):
        """
        Fetches the schedule of logged in user
        Returns an (not currently) ordered list with days going from index 0-4
        This list contains all events on that day
        """
        #TODO: Make sure the list is in order

        schedule_html = self.try_get("https://sms5.schoolsoft.se/{}/jsp/student/right_student_schedule.jsp?menu=schedule".format(self.school))
        schedule = BeautifulSoup(schedule_html.text, "html.parser")

        full_schedule = []

        for a in schedule.find_all("a", {"class": "schedule"}):
            info = a.find("span")
            info_pretty = info.get_text(separator=u"<br/>").split(u"<br/>")
            full_schedule.append(info_pretty)

        return full_schedule

    def fetch_news(self):
        """
        Fetches the news messages
        Returns a list of dicts, where each dict describes a message. The dict contains the following keys:
         * id   The message internal ID, as an int
         * subject   The message subject, as a string
         * body   The message body, as html text
         * category   The category the message belongs to, as a string
         * from   The sender, as a string
         * to   The recipient(s), as a string
         * date   The publish date, as a datetime.date
         * attachment-url   The URL to an attachment (optional), as a string
         * attachment-name   The name of the attachment (optional), as a string
        """
        news_html = self.try_get("https://sms5.schoolsoft.se/{}/jsp/student/right_student_news.jsp?menu=news".format(self.school))
        # normalize all of the html directly
        news_html_normalized = unicodedata.normalize("NFKC", news_html.text)

        # FIXME: Why does this not work?
        # news_html_normalized = news_html_normalized.replace(u'\xa0', u' ')
        news_soup = BeautifulSoup(news_html_normalized, "html.parser")
        news_items = []

        news_content_tag = news_soup.find("div", id="news_con_content")
        for category_tag in news_content_tag.find_all("div", {"class": "h3_bold"}):
            category = category_tag.get_text().strip()
            # Assume the next sibling will be the div id=accordion.
            category_items = category_tag.next_sibling
            for item_tag in category_items.contents:
                item = dict()
                item['category'] = category
                try:
                    item_tag_id = item_tag['id']
                    item['id'] = int(re.search('acc-item-(.*)', item_tag_id).group(1))
                except:
                    # We don't expect this to really happen.
                    item['id'] = 0

                # We must load the entire tag using Ajax if it was not already loaded
                msg_body = item_tag.find("span", id=re.compile("^description"))
                if not msg_body:
                    item_html = self.try_get(
                        "https://sms5.schoolsoft.se/{}/jsp/student/right_student_news_ajax.jsp?action=viewdetail&requestid={}&type=1".format(
                            self.school, item['id']))
                    item_tag = BeautifulSoup(item_html.text, "html.parser")
                    msg_body = item_tag.find("span", id=re.compile("^description"))

                msg_subject = item_tag.find("span", id=re.compile("^name"))
                item['subject'] = msg_subject.string.strip()
                # There seems to be no better way to extract the html code for a BS4 tag :(
                item['body'] = ''.join([str(elem) for elem in msg_body.contents]).strip().replace(u'\xa0', u' ')

                metadata = item_tag.find("div", class_="inner_right_info")
                for field in metadata.find_all("label"):
                    label_name = field.string
                    label_val = field.next_sibling
                    if label_name == "Från":
                        item['from'] = label_val.string
                    elif label_name == "Till":
                        item['to'] = label_val.string.replace(u'\xa0', u' ').strip()
                    elif label_name == "Publicerad":
                        date_day_tag = label_val.next_sibling
                        date_month_tag = date_day_tag.next_sibling
                        date_year_tag = date_month_tag.next_sibling
                        # For some weird reason, month is represented by the month number minus 1.
                        item['date'] = date(int(date_year_tag.string), int(date_month_tag.string)+1, int(date_day_tag.string))
                    elif label_name == "Bifogade filer":
                        # FIXME: Should support multiple files
                        # note href is relative to server... eg right_student_file_download.jsp?requestid1=133766&requestid2=1&object=news&fileid=143965
                        file_tag = label_val.find("a")
                        item['attachment-url'] = file_tag['href']
                        item['attachment-name'] = file_tag['title']
                        pass

                news_items.append(item)

        return news_items


if __name__ == "__main__":
    # Testing shit, uses my testkeys
    api = SchoolSoft(testkeys.school, testkeys.username, testkeys.password, testkeys.usertype)

    # Example calls
    lunch = api.fetch_lunch_menu()
    schedule = api.fetch_schedule()
    news = api.fetch_news()
