from pathlib import Path
from .errors import ToolError

class Tool:
    """
     Represents one thing the AI can do.
    
    Every tool has:
    - name: what the AI calls it
    - description: what it does (AI reads this to decide which tool to use)
    - schema: what arguments it accepts
    - fn: the actual Python function that runs
    - mutating: does it CHANGE something? (needs approval if yes)
    
    Example tool object:
    Tool(
        name = "read_file",
        description = "Read a file from the inbox",
        schema = {"type": "object", "properties": {"path": {"type": "string"}}},
        fn = read_file,
        mutating = False   # just reading, no approval needed
    )
    """

    def __init__(self,name,description,schema,fn,mutating=False):
        self.name = name
        self.description = description
        self.schema = schema
        self.fn = fn
        self.mutating = mutating   # True = changes real system = needs approval

    def spec(self):
        """
        Returns the tool in the format GenAi API expects.
        
        This is what gets sent to Claude so it knows
        what tools are available and how to call them.
        
        Looks like this:
        {
            "name": "read_file",
            "description": "Read a file...",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
        """
        return {
            "name":self.name,
            "description":self.description,
            "input_schema":self.schema
        }    


def make_schema(properties, required):
        """
        Shortcut to build the JSON schema for a tool.
        
        JSON schema tells Claude what arguments a tool accepts.
        
        Example:
        make_schema(
            properties = {
                "path": {"type": "string"},
                "max_chars": {"type": "integer"}
            },
            required = ["path"]   # path is mandatory, max_chars is optional
        )
        
        Returns:
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_chars": {"type": "integer"}
            },
            "required": ["path"]
        }
        """
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }


    ## File Tools

    # safety check
def safe_path(ctx, relative_path):
        """
        Converts a relative path to absolute and checks
    it's inside our workspace folder.
    
    Example:
    safe_path(ctx, "inbox/invoice.txt")
    → C:/Users/user/Desktop/autonomous-ai-worker/sandbox/workspace/inbox/invoice.txt
    
    safe_path(ctx, "../../passwords.txt")
    → RAISES ToolError (path escapes workspace!)
        """
        workspace =ctx.workspace.resolve()
        full_path = (workspace / relative_path).resolve()

        # check the path is still inside workspace
        if workspace!= full_path and workspace not in full_path.parents:
            raise ToolError(
                f"Path '{relative_path}' is outside the workspace. Access denied."
            )
        return full_path


def read_text_from_file(path):
        """
         Reads content from txt, html or pdf files.
    
    For PDF files we use pypdf to extract text.
    For everything else we just read the text directly.
        """

        if path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                #Join text from all pages
                return "\n".join(
                    page.extract_text() or "" for page in reader.pages
                )
            except ImportError:
                raise ToolError("pypdf not installed. Run: pip install pypdf")

        # For txt, html, md, csv etc
        return path.read_text(errors='replace')    

    ## tool1 list files

def list_files(ctx, path="."):
        """
        Lists files in a folder.
    
        Example call from AI:
        list_files(ctx, path="inbox")
        
        Returns:
        {
            "ok": True,
            "path": "inbox",
            "entries": [
                "2026-07-03_northwind_INV-2031.txt",
                "2026-08-15_northwind_INV-2044.html",
                "2026-09-11_globex_GLX-88121.pdf",
                "2026-09-22_northwind_INV-2057.txt",
                "2026-09-30_northwind_payment_reminder.txt"
            ]
        }
        
        AI reads this and decides which files to open.
        """
        p = safe_path(ctx,path)

        if not p.exists():
             raise ToolError(f"Path '{path}' does not exist.")
        if p.is_file():
             return {"ok":True, "entries":[path]}

        items = sorted(p.iterdir(),key=lambda x:x.name)    

        return {
             "ok": True,
             "path": path,
             "entries": [
            # Add / at end of folder names so AI knows they're folders
            f"{item.name}/" if item.is_dir() else item.name
            for item in items
        ]
        }


## tool2 read_file

def read_file(ctx,path,offset=0,max_chars=5000):
     """
     Reads content of a file.
    
    offset and max_chars allow reading large files in chunks.
    e.g. read first 5000 chars, then next 5000 etc.
    
    Example call from AI:
    read_file(ctx, path="inbox/2026-09-22_northwind_INV-2057.txt")
    
    Returns:
    {
        "ok": True,
        "path": "inbox/2026-09-22_northwind_INV-2057.txt",
        "content": "From: billing@northwind-traders.example\n
                    Invoice Number : INV-2057\n
                    Invoice Date   : 21 Sep 2026\n
                    Due Date       : 21 Oct 2026\n
                    TOTAL DUE      : 4,820.50",
        "total_chars": 487,
        "truncated": False
    }
    
    AI reads content and extracts:
    - invoice number: INV-2057
    - amount: 4820.50
    - due date: 2026-10-21
     """

     p = safe_path(ctx,path)

     if not p.is_file():
          raise ToolError(f"'{path}' is not a file.")

     text = read_text_from_file(p)
     chunk = text[offset:offset+max_chars]

     return {
          "ok": True,
        "path": path,
        "content": chunk,
        "total_chars": len(text),
        "offset": offset,
        "truncated": (offset + max_chars) < len(text)
     }

## Tool3 search files

def search_files(ctx,query,path="."):
     """
     Searches all files for a keyword.
    Like Ctrl+F but across all files.
    
    Example call from AI:
    search_files(ctx, query="Northwind", path="inbox")
    
    Returns:
    {
        "ok": True,
        "matches": [
            {
                "file": "inbox/2026-07-03_northwind_INV-2031.txt",
                "line": 4,
                "text": "From: billing@northwind-traders.example"
            },
            {
                "file": "inbox/2026-09-22_northwind_INV-2057.txt",
                "line": 4,
                "text": "From: billing@northwind-traders.example"
            }
        ]
    }
    
    AI uses this to quickly find which files contain
    relevant invoices without reading every single file.
     """

     root = safe_path(ctx,path)
     matches = []
     query_lower = query.lower()

     # walk through every file reccursively

     for file_path in sorted(root.rglob("*")):
          if not file_path.is_file():
               continue

          try:
               text=read_text_from_file(file_path)
          except Exception:
               continue

          for line_number,line in enumerate(text.splitlines(),start=1):
               if query_lower in line.lower():
                    matches.append({
                         "file":str(file_path.relative_to(ctx.workspace)),
                         "line":line_number,
                         "text":line.strip()[:200] # first 200 chars of matching line

                    })     
          if(len(matches)>=40):
               return {
                    "ok":True,
                    "matches":matches,
                    "note":"showing first 40 matches only"
               }           
     return {
         "ok": True, "matches": matches
    }      