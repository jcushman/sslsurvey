from collections import namedtuple
import csv
import requests
from requests.exceptions import SSLError, ConnectionError, ConnectTimeout, ReadTimeout
from jinja2 import Environment, FileSystemLoader
import os
import subprocess

# set up templates
this_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(this_dir, 'templates')
j2_env = Environment(loader=FileSystemLoader(template_dir))

# get data
data_source = 'https://docs.google.com/spreadsheets/d/1VlZwHxQ5y2cq39x_ZBKCtz82tahnhrqzlzHdxM-bjLo/pub?gid=0&single=true&output=csv'
data = requests.get(data_source).content

### helpers ###

def do_request(url):
    return requests.get(url, timeout=5)

def get_response_from_curl(url):
    response = subprocess.check_output(["curl", "-I", url])
    headers = {}
    lines = response.split("\r\n")
    for line in lines[1:]:
        if ': ' in line:
            key, val = line.split(': ')
            headers[key.lower()] = val
    return namedtuple('FakeResponse', 'headers url')(
        headers=headers,
        url=headers['location']
    )

### check sites ###

results = []
for row in csv.DictReader(data.split("\n")):
    result = {}
    results.append(result)
    result['url'] = url = row['Representative URL']
    result['name'] = row['Media']
    result['rank'] = row['Rank (According to Pew Research Center Analysis)']

    http_url = url.replace('https', 'http', 1)
    print url

    try:
        response = do_request(url)

    # problem connecting?
    except (SSLError, ConnectionError, ConnectTimeout, ReadTimeout) as e:
        assert do_request(http_url).ok  # make sure this is SSL-specific

        if type(e) == SSLError and 'handshake failure' in str(e):
            # handshake failure is probably a `requests` bug -- try a curl fallback
            response = get_response_from_curl(url)

        else:
            if type(e) == SSLError:
                error = e.args[0].args[0].args[0]
                for fingerprint, host in (('akamai', 'Akamai'), ('fastly', 'Fastly'), ('wordpress', 'Wordpress')):
                    if fingerprint in error:
                        error = host
                        break
                else:
                    import ipdb; ipdb.set_trace()
                result['message'] = "Invalid certificate: %s" % error
            else:
                result['message'] = "No response on port 443."
            result['ssl_support'] = False
            continue

    # redirect to insecure site?
    if response.url.startswith('http:'):
        result['message'] = "Redirected to insecure site%s." % ("" if response.url == http_url else " (%s)" % response.url)
        result['ssl_support'] = False
        continue

    # special cases
    if url in ['https://www.nydailynews.com/', 'https://www.theatlantic.com/']:
        result['message'] = "SSL works, but rendering is broken because all page assets load from HTTP."
        result['ssl_support'] = False
        continue

    # you support ssl! how do you handle non-ssl?
    result['ssl_support'] = True
    http_response = do_request(http_url)
    if http_response.url.startswith('https:'):
        result['message'] = "Bonus! Redirected to secure site%s." % ("" if http_response.url == url else " (%s)" % http_response.url)

    # whitelist of sites confirmed working on https
    if url in ['https://news.yahoo.com/', 'https://www.washingtonpost.com/', 'https://www.msn.com/', 'https://www.upworthy.com/', 'https://www.vox.com/', 'https://www.salon.com/', 'https://www.bostonglobe.com/', 'https://www.boston.com/']:
        continue

    # if we get here, something surprising has happened
    import ipdb; ipdb.set_trace()

print "Got data:", results

# output results
open(os.path.join(this_dir, 'output/index.html'), 'w').write(j2_env.get_template('index.html').render(results=results))