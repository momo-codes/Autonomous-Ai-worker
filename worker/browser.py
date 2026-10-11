import requests
from urllib.parse import urljoin, urlparse
from .errors import ToolError
from bs4 import BeautifulSoup
import re

MAX_TEXT = 4000


class Browser:

    def __init__(self, allowed_hosts):
        self.session = requests.Session()
        self.allowed_hosts = set(allowed_hosts)
        self.current_url = None
        self.forms = []

    def open(self, url):
        if self.current_url:
            url = urljoin(self.current_url, url)
        self._check_host(url)
        response = self._get(url)
        return self._parse_page(response)

    def submit(self, form_index, fields):
        if not self.forms:
            raise ToolError(
                "No forms on current page. Call browser_open first."
            )
        if form_index >= len(self.forms):
            raise ToolError(
                f"Form index {form_index} does not exist. "
                f"Page has {len(self.forms)} forms (0 to {len(self.forms)-1})"
            )

        form = self.forms[form_index]

        # Start with ALL existing values (includes hidden csrf_token)
        data = {}
        for field in form["fields"]:
            if field["name"]:
                data[field["name"]] = field.get("value", "")

        # Apply what AI wants to set
        known_fields = {f["name"]: f for f in form["fields"]}
        for name, value in fields.items():
            if name not in known_fields:
                raise ToolError(
                    f"Field '{name}' does not exist. "
                    f"Known fields: {sorted(known_fields.keys())}"
                )
            field = known_fields[name]
            if field.get("options"):
                value = self._match_option(field, value)
            data[name] = str(value) if value is not None else ""

        action_url = form["action"]
        self._check_host(action_url)
        previous_forms = self.forms

        if form["method"] == "GET":
            response = self._get(action_url, params=data)
        else:
            response = self._post(action_url, data=data)

        result = self._parse_page(response)

        if not result["ok"] and not self.forms:
            self.forms = previous_forms
            result["forms"] = previous_forms
            result["note"] = (
                "Error page had no form. "
                "Previous form restored so you can fix and retry."
            )
        return result

    def describe_submission(self, form_index, fields):
        if not self.forms or form_index >= len(self.forms):
            return f"submit form #{form_index} with fields {fields}"
        form = self.forms[form_index]
        return f"{form['method']} {form['action']} with fields {fields}"

    def _check_host(self, url):
        host = urlparse(url).netloc
        if host not in self.allowed_hosts:
            raise ToolError(
                f"Host '{host}' is not allowed. "
                f"Allowed: {sorted(self.allowed_hosts)}"
            )

    def _get(self, url, params=None):
        try:
            return self.session.get(url, params=params, timeout=10)
        except requests.RequestException as e:
            raise ToolError(f"Network error: {e}")

    def _post(self, url, data=None):
        try:
            return self.session.post(url, data=data, timeout=10)
        except requests.RequestException as e:
            raise ToolError(f"Network error: {e}")

    def _match_option(self, field, value):
        value = str(value).strip()
        options = field.get("options", [])
        for opt in options:
            if value == opt["value"]:
                return opt["value"]
        for opt in options:
            if value.lower() == opt["label"].strip().lower():
                return opt["value"]
        raise ToolError(
            f"'{value}' is not valid for '{field['name']}'. "
            f"Options: {[o['label'] for o in options]}"
        )

    def _parse_page(self, response):
        self.current_url = response.url
        soup = BeautifulSoup(response.text, "html.parser")

        self.forms = []
        for i, form_tag in enumerate(soup.find_all("form")):
            self.forms.append(self._parse_form(form_tag, i))

        links = []
        for a in soup.find_all("a", href=True):
            links.append({
                "text": a.get_text(strip=True),
                "href": urljoin(response.url, a["href"])
            })

        for form_tag in soup.find_all("form"):
            form_tag.decompose()

        for tr in soup.find_all("tr"):
            cells = [
                td.get_text(" ", strip=True)
                for td in tr.find_all(["td", "th"])
            ]
            tr.replace_with(" | ".join(cells) + "\n")

        text = soup.get_text(separator="\n")
        text = re.sub(r"\n\s*\n+", "\n", text).strip()

        if len(text) > MAX_TEXT:
            text = text[:MAX_TEXT] + "\n...[page truncated]"

        return {
            "ok": response.status_code < 400,
            "status": response.status_code,
            "url": response.url,
            "title": soup.title.get_text(strip=True) if soup.title else "",
            "text": text,
            "links": links[:20],
            "forms": self.forms
        }

    def _parse_form(self, form_tag, index):
        fields = []

        for el in form_tag.find_all(["input", "select", "textarea"]):
            name = el.get("name")
            if not name or el.get("type") in ("submit", "button"):
                continue

            field = {
                "name": name,
                "type": el.get("type", el.name),
                "required": el.has_attr("required"),
                "value": ""
            }

            if el.name == "select":
                options = []
                for opt in el.find_all("option"):
                    val = opt.get("value", opt.get_text(strip=True))
                    if val:
                        options.append({
                            "value": val,
                            "label": opt.get_text(strip=True)
                        })
                selected = el.find("option", selected=True)
                field["options"] = options
                field["value"] = selected.get("value", "") if selected else ""

            elif el.name == "textarea":
                field["value"] = el.get_text()
            else:
                field["value"] = el.get("value", "")

            fields.append(field)

        method = (form_tag.get("method") or "GET").upper()
        action = urljoin(
            self.current_url,
            form_tag.get("action") or self.current_url
        )

        return {
            "index": index,
            "method": method,
            "action": action,
            "fields": fields
        }   