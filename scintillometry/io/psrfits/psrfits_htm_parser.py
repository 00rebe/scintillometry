from html.parser import HTMLParser
from astropy.io import fits


class MyHTMLParser(HTMLParser):
    section = False
    collect = False
    add_nl = False
    extensions = {}
    extname = ''
    data = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'p' or (tag == 'div' and attrs == [('class', 'indent')]):
            self.collect = True
            self.data = ''
        elif tag == 'br':
            self.add_nl = True
        elif tag == 'h3':
            if self.section:
                self.dump()
            self.section = True
            self.headers = []

    def handle_endtag(self, tag):
        if tag not in ('p', 'div') or not self.collect:
            return

        self.collect = False
        data = self.data
        if tag == 'p' and (
                data.startswith('COMMENT') or
                data.startswith('END') or
                (len(data) > 8 and data[8] == '=')):
            if data.startswith('EXTNAME'):
                self.extname = data.split(' ')[2]
            self.headers += data.split('\n')
            self.collect = False
        elif tag == "div" and self.headers and (
                not data.startswith('Standard')):
            # description for last header.
            self.headers[-1] = self.headers[-1] + '\n# ' + data

    def handle_data(self, data):
        data = data.replace('\n', '')
        if self.collect:
            self.data += ('\n' if self.add_nl else '') + data
        self.add_nl = False

    def dump(self):
        self.extensions[self.extname] = '\n'.join(self.headers)


parser = MyHTMLParser()

f = open('PsrfitsDocumentation.html')
parser.feed(f.read())
print(parser.extensions[''])
