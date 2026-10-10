"""
A text-based web browser the AI can control.

Why text instead of screenshots?
- Cheaper and faster than visual AI
- Every element is explicitly readable
- Easy to test and debug
- The form fields (including hidden ones like CSRF tokens)
  are automatically exposed to the AI

How it works:
1. AI calls browser_open(url)
2. We fetch the page with requests (like fetch() in Node)
3. We parse it with BeautifulSoup
4. We return: page text + all links + all forms with every field
5. AI reads this and decides what to fill in
6. AI calls browser_submit(form_index, fields)
7. We auto-fill hidden fields, submit, return the result

The AI only needs to supply the fields a human would type.
Hidden fields like CSRF tokens are filled automatically.
"""
import requests
from urllib.parse import urljoin , urlparse
from .errors import ToolError
from bs4 import BeautifulSoup
import re

MAX_TEXT = 4000

class Browser:
    def __init__(self,allowed_hosts):
        """
        allowed_hosts: set of hostnames the browser can visit
        e.g. {"127.0.0.1:5055"}

        This prevents the AI from accidentally (or intentionally)
        visiting external websites
        """
        # requests.Session() is like keeping cookies between requests
        # Just like a browser remebers your login session
        self.session = requests.Session()
        self.allowed_hosts = set(allowed_hosts)
        self.current_url = None
        self.forms = [] # forms found on the current form

        # PUBLIC METHODS (what the agent calls)

        def open(self,url):
            """
            opens a URL and returns the page text, links, and forms
            """
            # handle relative urls like "/payables" -> "http://127.0.0.1:5055/payables
            if self.current_url:
                url= urljoin(self.current_url,url)

            #Security check --> only allowed hosts
            self._check_host(url) 

            # Fetch the page
            response= self._get(url)
            return self._parse_page(response)

        def submit(self,form_index,fields):
            """
            submits  form on the current page 
            form_index: which form(0==first form)
            fields: dict of field names and values to fill in

            hidden fields like CSRF tokens are filled automatically
            the AI only needs to supply the fields a human would type
            """

            if not self.forms:
                raise ToolError("No forms on the current page.Call browser_open(url) first.")

            if form_index>=len(self.forms):
                raise ToolError(
                    f"Form index does not exist. "
                    f"This page has {len(self.forms)} forms (0 to {len(self.forms)-1})"
                )

            form = self.forms[form_index]

            # Start with all existing field values (includes hidden fields)
            # This is the key feature - CSRF tokens etc are pre-filled

            data={}
            for field in form["fields"]:
                if field["name"]:
                    data[field["name"]] = field.get("value","")

            # now apply what the ai wants to set

            known_fields = {f["name"]:f for f in form["fields"]}

            for name, value in fields.items():
                if name not in known_fields:
                    raise ToolError(f"Field '{name}' does not exist in the form. Known fields: {sorted(known_fields.keys())}")
                field = known_fields[name]
                if field.get("options"):
                    value = self._match_option(field,value)
                data[name] = str(value) if value is not None else ""

            # Submit the form
            action_url = form["action"] 
            self._check_host(action_url)

            # save form before requests in case the error page has no forms
            previous_forms = self.forms    
            if form["method"]=="GET":
                response =  self._get(action_url,params =data)
            else:
                response = self._post(action_url,data=data)
            result = self._parse_page(response)

            #if error page has no forms restore prev form so that ai can fix and try without reloading
            if not result["ok"] and not self.forms:
                self.forms= previous_forms
                result["forms"]=previous_forms
                result["note"]=(
                    "Error page had no form. "
                "Previous form restored so you can fix and retry."
                )        
            return result


def describe_submission(self, form_index, fields):
        """
        Returns human-readable description of what would be submitted.
        Used by the approval system to show humans what the AI wants to do.
        """
        if not self.forms or form_index >= len(self.forms):
            return f"submit form #{form_index} with fields {fields}"

        form = self.forms[form_index]
        return f"{form['method']} {form['action']} with fields {fields}"            

## INTERNAL METHODs

def _check_host(self,url):
    """
    Block requests to host not on allow list
    """
    host = urlparse(url).netloc
    if host not in self.allowed_hosts:
        raise ToolError(
            f"Host '{host}' is not allowed"
            f"Allowed hosts: {sorted(self.allowed_hosts)}"
        )

def _get(self,url,params=None):
    """Makes a GET request"""
    try:
        return self.session.get(url,params=params,timeout =10)
    except requests.RequestException as e:
        raise ToolError(f"Network error: {e}")

def _post(self,url,data=None):
    """makes a post request"""
    try:
        return self.session.post(url,data = data,timeout=10)
    except requests.RequestException as e:
        raise ToolError(f"network error: {e}")  
          
def _match_option(self,field,value):
    """
    For dropdown fields, match by value OR by label text.
        e.g. AI can say "Northwind Traders Pvt Ltd" and we find "V-100"
    """
    value= str(value).strip()
    options = field.get("options",[]);

    # try exact value match first

    for opt in options:
        if value == opt["value"]:
            return opt["value"]

    # try label match
    for opt in options:
        if value.lower() == opt['label'].strip().lower():
            return opt["value"]

    raise ToolError(
        f"'{value}' is not valid for field '{field['name']}'. "
            f"Options are: {[o['label'] for o in options]}"
    )        

def _parse_page(self,response):
    """
        Converts an HTML page into structured data the AI can read.
        Returns: text content + links + forms with all fields
        """
    self.current_url = response.url
    soup = BeautifulSoup(response.text,"html.parser")

    #parse all forms before removing them from text
    self.forms = []
    for i, form_tag in enumerate(soup.find_all("form")):
        self.forms.append(self._parse_form(form_tag,i))

    # parse links
    links=[]
    for a in soup.find_all("a",href=True):
        links.append({
            "text":a.get_text(strp=True),
            "href":urljoin(response.url,a["href"])
        })    

    # remove forms from text so it looks clean 
    for form_tag in soup.find_all("form"):
        form_tag.decompose()

    # convert tables to readable text
    for tr in soup.find_all("tr"):
        cells=[
            td.get_text(" ",strip=True)
            for td in tr.find_all(["td","th"])
        ]        
        tr.replace_with(" | ".join(cells) + "\n")

    #get clean text
    text = soup.get_text(seperator="\n")
    text = re.sub(r"\n\s*\n+","\n",text).strip()

    #truncate if too long
    if(len(text)>MAX_TEXT):
        text = text[:MAX_TEXT]+"\n...[page truncated]"

    return {
        "ok":response.status_code<400,
        "status":response.status_code,
        "url":response.url,
        "title":soup.title.get_text(strip=True) if soup.title else "",
        "text":text,
        "links":links[:20],
        "forms":self.forms
    }    

def _parse_form(self,form_tag,index):
    """
     Extracts all fields from a form including hidden ones.
        This is how the AI sees the CSRF token automatically.
    """
    fields = []

    for el in form_tag.find_all(["input","select","textarea"]):
        name = el.get("name")
        # skip submit buttons
        if not name or el.get("type") in ("submit","button"):
            continue

        field ={
            "name":name,
            "type":el.get("type",el.name),
            "required":el.has_attr("required"),
            "value":""
        }

        if el.name=="select":
            #extract all dropdown options
            options=[]
            for opt in el.find_all("option"):
                val = opt.get("value",opt.get_text(strip=True))
                if val:
                    options.append({
                        "value":val,
                        "label":opt.get_text(strip=True)
                    })

                # get currently selected options
                selected = el.find("options",selected=True)
                field["options"] = options
                field["value"] = selected.get("value", "") if selected else ""
        elif el.name == "textarea":
                field["value"] = el.get_text()
        else:
                field["value"] = el.get("value", "")

        fields.append(field)

        method = (form_tag.get("method") or "GET").upper()
        action = urljoin(self.current_url, form_tag.get("action") or self.current_url)

        return {
            "index": index,
            "method": method,
            "action": action,
            "fields": fields
        }        