"""
PPTX Merger Service.

Handles merging of multiple PowerPoint presentations into a single file
while preserving styles, layouts, and masters by manipulating the OPC package directly.
"""
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

NAMESPACES = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
    'd': 'http://schemas.openxmlformats.org/drawingml/2006/diagram',
    'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
    'ct': 'http://schemas.openxmlformats.org/package/2006/content-types'
}

for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

class PPTXMerger:
    """
    Merges slides from multiple PPTX files into a single PPTX file.
    """
    
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.temp_dir = Path(tempfile.mkdtemp())
        self.work_dir = self.temp_dir / "work"
        self.sources_dir = self.temp_dir / "sources"
        self.work_dir.mkdir()
        self.sources_dir.mkdir()
        
        self.slides: List[Tuple[str, int]] = [] # (source_id, slide_index)
        self.source_map: Dict[str, Path] = {} # source_id -> path
        self.extracted_sources: Dict[str, Path] = {} # source_id -> extracted_path
        
        self.imported_parts: Dict[Tuple[str, str], str] = {}
        
        self.imported_content_types: Dict[str, str] = {}
        
        self.next_ids = {
            'slide': 1,
            'slideLayout': 1,
            'slideMaster': 1,
            'theme': 1,
            'media': 1,
            'notesSlide': 1,
            'notesMaster': 1,
            'unknown': 1
        }
        
        self.source_content_types: Dict[str, Dict[str, str]] = {}

    def add_slide(self, source_path: Path, slide_index: int):
        """Add a slide to the merge list."""
        source_id = str(source_path)
        if source_id not in self.source_map:
            self.source_map[source_id] = source_path
        
        self.slides.append((source_id, slide_index))
        
    def merge(self):
        """Execute the merge process."""
        try:
            if not self.slides:
                raise ValueError("No slides to merge")
            
            self._extract_sources()
            
            base_source_id = self.slides[0][0]
            self._prepare_base(base_source_id)
            
            self._process_slides()
            
            self._repackage()
            
        finally:
            self._cleanup()
            
    def _extract_sources(self):
        """Extract all source PPTX files."""
        for source_id, path in self.source_map.items():
            extract_path = self.sources_dir / str(uuid.uuid4())
            self.extracted_sources[source_id] = extract_path
            with zipfile.ZipFile(path, 'r') as zf:
                zf.extractall(extract_path)
                
    def _prepare_base(self, base_source_id: str):
        """Copy the base source to the work directory."""
        base_path = self.extracted_sources[base_source_id]
        shutil.copytree(base_path, self.work_dir, dirs_exist_ok=True)
        
        self._scan_base_content(base_source_id)

    def _scan_base_content(self, base_source_id: str):
        """Scan the work directory to populate imported_parts and update next_ids."""
        ppt_dir = self.work_dir / "ppt"
        
        def update_id(prefix, filename):
            match = re.search(rf"{prefix}(\d+)\.", filename)
            if match:
                num = int(match.group(1))
                if num >= self.next_ids.get(prefix, 1):
                    self.next_ids[prefix] = num + 1

        for root, dirs, files in os.walk(ppt_dir):
            for file in files:
                rel_path = Path(root).relative_to(ppt_dir) / file
                rel_path_str = str(rel_path)
                
                if file.startswith("slideLayout"):
                    update_id("slideLayout", file)
                elif file.startswith("slideMaster"):
                    update_id("slideMaster", file)
                elif file.startswith("slide"):
                    update_id("slide", file)
                elif file.startswith("theme"):
                    update_id("theme", file)
                elif file.startswith("image") or file.startswith("media"):
                    match = re.search(r"image(\d+)\.", file)
                    if match:
                        num = int(match.group(1))
                        if num >= self.next_ids['media']:
                            self.next_ids['media'] = num + 1
                
                self.imported_parts[(base_source_id, rel_path_str)] = rel_path_str

    def _process_slides(self):
        """Rebuild presentation.xml and import slides."""
        pres_xml_path = self.work_dir / "ppt" / "presentation.xml"
        pres_tree = ET.parse(pres_xml_path)
        pres_root = pres_tree.getroot()
        
        sld_id_lst = pres_root.find("p:sldIdLst", NAMESPACES)
        if sld_id_lst is not None:
            for child in list(sld_id_lst):
                sld_id_lst.remove(child)
        else:
            sld_id_lst = ET.SubElement(pres_root, f"{{{NAMESPACES['p']}}}sldIdLst")
            
        ext_lst = pres_root.find("p:extLst", NAMESPACES)
        if ext_lst is not None:
            pres_root.remove(ext_lst)
            
        cust_show_lst = pres_root.find("p:custShowLst", NAMESPACES)
        if cust_show_lst is not None:
            pres_root.remove(cust_show_lst)
            
        pres_rels_path = self.work_dir / "ppt" / "_rels" / "presentation.xml.rels"
        pres_rels_tree = ET.parse(pres_rels_path)
        pres_rels_root = pres_rels_tree.getroot()
        
        for rel in list(pres_rels_root.findall(f"{{{NAMESPACES['rel']}}}Relationship")):
            if rel.get("Type") == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide":
                pres_rels_root.remove(rel)
        
        existing_rIds = [int(rel.get("Id")[3:]) for rel in pres_rels_root.findall(f"{{{NAMESPACES['rel']}}}Relationship") if rel.get("Id").startswith("rId")]
        if existing_rIds:
            self.next_rId = max(existing_rIds) + 1
        else:
            self.next_rId = 1000
            
        self.next_slide_id_attr = 256
        
        self.existing_masters = set()
        sld_master_id_lst = pres_root.find("p:sldMasterIdLst", NAMESPACES)
        if sld_master_id_lst is not None:
            for child in sld_master_id_lst:
                rId = child.get(f"{{{NAMESPACES['r']}}}id")
                for rel in pres_rels_root.findall(f"{{{NAMESPACES['rel']}}}Relationship"):
                    if rel.get("Id") == rId:
                        self.existing_masters.add(rel.get("Target"))
        else:
            sld_master_id_lst = ET.SubElement(pres_root, f"{{{NAMESPACES['p']}}}sldMasterIdLst")

        self.next_master_id_attr = 2147483648
        if sld_master_id_lst is not None:
             ids = [int(child.get("id")) for child in sld_master_id_lst.findall("p:sldMasterId", NAMESPACES)]
             if ids:
                 self.next_master_id_attr = max(ids) + 1

        for source_id, slide_index in self.slides:
            slide_part_path = self._get_source_slide_part(source_id, slide_index)
            
            if not slide_part_path:
                logger.warning(f"Could not find slide {slide_index} in {source_id}")
                continue
                
            new_slide_part = self._import_part(source_id, slide_part_path, "slides")
            
            self._ensure_master_registered(source_id, slide_part_path, pres_root, pres_rels_root, sld_master_id_lst)

            rId = f"rId{self.next_rId}"
            self.next_rId += 1
            
            rel = ET.SubElement(pres_rels_root, f"{{{NAMESPACES['rel']}}}Relationship")
            rel.set("Id", rId)
            rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide")
            rel.set("Target", new_slide_part)
            
            sld_id = ET.SubElement(sld_id_lst, f"{{{NAMESPACES['p']}}}sldId")
            sld_id.set("id", str(self.next_slide_id_attr))
            sld_id.set(f"{{{NAMESPACES['r']}}}id", rId)
            self.next_slide_id_attr += 1
            
        pres_tree.write(pres_xml_path)
        pres_rels_tree.write(pres_rels_path)
        
        self._update_content_types()

    def _ensure_master_registered(self, source_id: str, slide_part_path: str, pres_root, pres_rels_root, sld_master_id_lst):
        """Ensure the master used by the slide is registered in presentation.xml."""
        new_slide_path = self.imported_parts.get((source_id, slide_part_path))
        if not new_slide_path:
            return

        slide_rels_path = self.work_dir / "ppt" / Path(new_slide_path).parent / "_rels" / f"{Path(new_slide_path).name}.rels"
        if not slide_rels_path.exists():
            return
            
        layout_path = None
        tree = ET.parse(slide_rels_path)
        for rel in tree.getroot():
            if "slideLayout" in rel.get("Type"):
                layout_path = rel.get("Target")
                break
        
        if not layout_path:
            return
            
        layout_full_path = (self.work_dir / "ppt" / Path(new_slide_path).parent / layout_path).resolve()
        try:
            layout_rel_ppt = layout_full_path.relative_to(self.work_dir / "ppt")
        except ValueError:
            return
            
        layout_rels_path = self.work_dir / "ppt" / layout_rel_ppt.parent / "_rels" / f"{layout_rel_ppt.name}.rels"
        if not layout_rels_path.exists():
            return
            
        master_path = None
        tree = ET.parse(layout_rels_path)
        for rel in tree.getroot():
            if "slideMaster" in rel.get("Type"):
                master_path = rel.get("Target")
                break
                
        if not master_path:
            return

        master_full_path = (self.work_dir / "ppt" / layout_rel_ppt.parent / master_path).resolve()
        try:
            master_rel_ppt = str(master_full_path.relative_to(self.work_dir / "ppt"))
        except ValueError:
            return
            
        master_rel_ppt = master_rel_ppt.replace("\\", "/")
        
        is_registered = False
        for existing in self.existing_masters:
            if existing.replace("\\", "/") == master_rel_ppt:
                is_registered = True
                break
                
        if not is_registered:
            rId = f"rId{self.next_rId}"
            self.next_rId += 1
            
            rel = ET.SubElement(pres_rels_root, f"{{{NAMESPACES['rel']}}}Relationship")
            rel.set("Id", rId)
            rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster")
            rel.set("Target", master_rel_ppt)
            
            master_id = ET.SubElement(sld_master_id_lst, f"{{{NAMESPACES['p']}}}sldMasterId")
            master_id.set("id", str(self.next_master_id_attr))
            master_id.set(f"{{{NAMESPACES['r']}}}id", rId)
            self.next_master_id_attr += 1
            
            self.existing_masters.add(master_rel_ppt)

    def _get_source_slide_part(self, source_id: str, slide_index: int) -> Optional[str]:
        """Find the part path (e.g., 'slides/slide1.xml') for a given slide index."""
        source_path = self.extracted_sources[source_id]
        pres_xml = source_path / "ppt" / "presentation.xml"
        pres_rels = source_path / "ppt" / "_rels" / "presentation.xml.rels"
        
        if not pres_xml.exists():
            return None
            
        tree = ET.parse(pres_xml)
        root = tree.getroot()
        sld_id_lst = root.find("p:sldIdLst", NAMESPACES)
        
        if sld_id_lst is None:
            return None
            
        slides = list(sld_id_lst.findall("p:sldId", NAMESPACES))
        if slide_index > len(slides) or slide_index < 1:
            return None
            
        slide_node = slides[slide_index - 1]
        rId = slide_node.get(f"{{{NAMESPACES['r']}}}id")
        
        rels_tree = ET.parse(pres_rels)
        rels_root = rels_tree.getroot()
        for rel in rels_root.findall(f"{{{NAMESPACES['rel']}}}Relationship"):
            if rel.get("Id") == rId:
                return rel.get("Target")
                
        return None

    def _get_source_content_type(self, source_id: str, part_path: str) -> Optional[str]:
        """Get the content type of a part from the source's [Content_Types].xml."""
        if source_id not in self.source_content_types:
            self.source_content_types[source_id] = self._load_content_types(self.extracted_sources[source_id])
            
        candidates = [
            f"/ppt/{part_path}",
            f"/{part_path}",
            part_path
        ]
        
        ext = Path(part_path).suffix.lstrip('.').lower()
        
        types = self.source_content_types[source_id]
        
        for candidate in candidates:
            if candidate in types['overrides']:
                return types['overrides'][candidate]
                
        if ext in types['defaults']:
            return types['defaults'][ext]
            
        return None

    def _load_content_types(self, root_path: Path) -> Dict[str, Dict[str, str]]:
        """Load content types from a directory."""
        ct_path = root_path / "[Content_Types].xml"
        if not ct_path.exists():
            return {'defaults': {}, 'overrides': {}}
            
        tree = ET.parse(ct_path)
        root = tree.getroot()
        
        defaults = {}
        overrides = {}
        
        for child in root:
            if child.tag.endswith("Default"):
                defaults[child.get("Extension").lower()] = child.get("ContentType")
            elif child.tag.endswith("Override"):
                overrides[child.get("PartName")] = child.get("ContentType")
                
        return {'defaults': defaults, 'overrides': overrides}

    def _import_part(self, source_id: str, part_path: str, part_type: str) -> str:
        """
        Import a part from source to work dir.
        part_path: relative to 'ppt/' (e.g., 'slides/slide1.xml')
        part_type: 'slides', 'slideLayouts', 'slideMasters', 'theme', 'media'
        Returns: new path relative to 'ppt/'
        """
        if part_path.startswith("/"):
            part_path = part_path[1:]
            
        cache_key = (source_id, part_path)
        if cache_key in self.imported_parts:
            return self.imported_parts[cache_key]
            
        ext = Path(part_path).suffix
        prefix = part_type.rstrip('s')
        
        if part_type == "media":
            new_filename = f"image{self.next_ids['media']}{ext}"
            self.next_ids['media'] += 1
            new_part_path = f"media/{new_filename}"
        elif part_type == "unknown":
             name = Path(part_path).stem
             new_filename = f"{name}_{self.next_ids['unknown']}{ext}"
             self.next_ids['unknown'] += 1
             new_part_path = f"other/{new_filename}"
        else:
            folder = part_type
            if part_type == "theme":
                folder = "theme"
            
            new_filename = f"{prefix}{self.next_ids.get(prefix, 1)}{ext}"
            self.next_ids[prefix] = self.next_ids.get(prefix, 1) + 1
            new_part_path = f"{folder}/{new_filename}"

        source_full_path = self.extracted_sources[source_id] / "ppt" / part_path
        
        if not source_full_path.exists():
            source_full_path = (self.extracted_sources[source_id] / "ppt" / part_path).resolve()
            
        if not source_full_path.exists():
            logger.error(f"Part not found: {source_full_path}")
            return part_path
            
        dest_full_path = self.work_dir / "ppt" / new_part_path
        dest_full_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy(source_full_path, dest_full_path)
        self.imported_parts[cache_key] = new_part_path
        
        ct = self._get_source_content_type(source_id, part_path)
        if ct:
            self.imported_content_types[f"/ppt/{new_part_path}"] = ct
        
        if ext == ".xml":
            self._process_relationships(source_id, part_path, new_part_path)
            
        return new_part_path

    def _get_relationship_target_type(self, type_str: str, target_path: str) -> str:
        """Determine the internal type of a relationship target."""
        if "slideLayout" in type_str:
            return "slideLayouts"
        elif "slideMaster" in type_str:
            return "slideMasters"
        elif "theme" in type_str:
            return "theme"
        elif "image" in type_str:
            return "media"
        elif "video" in type_str:
            return "media"
        elif "audio" in type_str:
            return "media"
        elif "media" in type_str:
            return "media"
        elif "slide" in type_str:
            return "slides"
        
        ext = Path(target_path).suffix.lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.tiff', '.ico']:
            return "media"
        if ext in ['.mp4', '.avi', '.mov', '.wmv', '.m4v']:
            return "media"
        if ext in ['.mp3', '.wav', '.wma', '.m4a']:
            return "media"
            
        return "unknown"

    def _process_relationships(self, source_id: str, old_part_path: str, new_part_path: str):
        """Process relationships for a copied part."""
        old_path_obj = Path(old_part_path)
        rels_filename = f"{old_path_obj.name}.rels"
        old_rels_path = old_path_obj.parent / "_rels" / rels_filename
        
        source_rels_full = self.extracted_sources[source_id] / "ppt" / old_rels_path
        
        if not source_rels_full.exists():
            return
            
        tree = ET.parse(source_rels_full)
        root = tree.getroot()
        
        for rel in root.findall(f"{{{NAMESPACES['rel']}}}Relationship"):
            target = rel.get("Target")
            type_ = rel.get("Type")
            
            target_type = self._get_relationship_target_type(type_, target)
            
            if target.startswith("/"):
                target_full_in_source = (self.extracted_sources[source_id] / target.lstrip("/")).resolve()
            else:
                base_dir = old_path_obj.parent
                
                part_dir_abs = self.extracted_sources[source_id] / "ppt" / base_dir
                
                target_full_in_source = (part_dir_abs / target).resolve()
            
            ppt_dir_in_source = (self.extracted_sources[source_id] / "ppt").resolve()
            
            try:
                target_relative_to_ppt = target_full_in_source.relative_to(ppt_dir_in_source)
            except ValueError:
                continue
                
            new_target_relative_to_ppt = self._import_part(source_id, str(target_relative_to_ppt), target_type)
            
            new_part_dir = (self.work_dir / "ppt" / new_part_path).parent
            new_target_full = self.work_dir / "ppt" / new_target_relative_to_ppt
            
            new_target_relative = os.path.relpath(new_target_full, new_part_dir)
            rel.set("Target", new_target_relative)
            
        new_path_obj = Path(new_part_path)
        new_rels_dir = self.work_dir / "ppt" / new_path_obj.parent / "_rels"
        new_rels_dir.mkdir(parents=True, exist_ok=True)
        new_rels_path = new_rels_dir / f"{new_path_obj.name}.rels"
        
        tree.write(new_rels_path)

    def _update_content_types(self):
        """Update [Content_Types].xml with all files in work dir."""
        ct_path = self.work_dir / "[Content_Types].xml"
        tree = ET.parse(ct_path)
        root = tree.getroot()
        
        existing_overrides = set()
        for child in root.findall(f"{{http://schemas.openxmlformats.org/package/2006/content-types}}Override"):
            existing_overrides.add(child.get("PartName"))
            
        for part_name, ct in self.imported_content_types.items():
            if part_name not in existing_overrides:
                override = ET.SubElement(root, f"{{http://schemas.openxmlformats.org/package/2006/content-types}}Override")
                override.set("PartName", part_name)
                override.set("ContentType", ct)
                existing_overrides.add(part_name)
                
        pres_part = "/ppt/presentation.xml"
        if pres_part not in existing_overrides:
             override = ET.SubElement(root, f"{{http://schemas.openxmlformats.org/package/2006/content-types}}Override")
             override.set("PartName", pres_part)
             override.set("ContentType", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml")
             
        tree.write(ct_path)

    def _repackage(self):
        """Zip the work directory into the output file."""
        with zipfile.ZipFile(self.output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(self.work_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(self.work_dir)
                    zf.write(file_path, arcname)
                    
    def _cleanup(self):
        """Remove temporary directories."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)


def _download_pptx(url: str, dest_path: Path) -> bool:
    """
    Download a PPTX file from URL.
    
    Args:
        url: Download URL for the PPTX
        dest_path: Path where the file should be saved
        
    Returns:
        True if download was successful, False otherwise
    """
    import requests
    from config import get_settings
    
    settings = get_settings()
    
    try:
        logger.info(f"Downloading PPTX from {url}")
        headers = {"User-Agent": "Mozilla/5.0 (SlideFinderBot/1.0)"}
        response = requests.get(url, headers=headers, timeout=settings.pptx_download_timeout)
        
        if response.status_code == 200:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(response.content)
            logger.info(f"Successfully downloaded {dest_path.name}")
            return True
        else:
            logger.warning(f"Download failed with status {response.status_code}: {url}")
            return False
    except Exception as e:
        logger.error(f"Download error for {url}: {e}")
        return False


def merge_slides_to_deck(
    slide_specs: List[Tuple[str, int]],
    output_path: Path,
    ppts_dir: Path
) -> Path:
    """
    Merge slides from multiple PPTX files into a single deck.
    Downloads missing PPTX files on-demand if the URL is available in the index.
    
    Args:
        slide_specs: List of (session_code, slide_number) tuples
        output_path: Path where the merged PPTX should be saved
        ppts_dir: Directory containing source PPTX files
        
    Returns:
        Path to the generated PPTX file
    """
    # Import search service for looking up download URLs
    from services.search_service import SearchService
    search_service = SearchService()
    
    merger = PPTXMerger(output_path)
    
    for session_code, slide_number in slide_specs:
        source_pptx = ppts_dir / f"{session_code}.pptx"
        
        # Try to download if file doesn't exist
        if not source_pptx.exists():
            logger.info(f"PPTX not found locally, attempting download: {session_code}")
            ppt_url = search_service.get_ppt_url_for_session(session_code)
            
            if ppt_url:
                if not _download_pptx(ppt_url, source_pptx):
                    logger.warning(f"Failed to download PPTX for {session_code}")
                    continue
            else:
                logger.warning(f"No download URL found for session: {session_code}")
                continue
        
        if source_pptx.exists():
            merger.add_slide(source_pptx, slide_number)
        else:
            logger.warning(f"Source PPTX still not available: {source_pptx}")
    
    merger.merge()
    return output_path
