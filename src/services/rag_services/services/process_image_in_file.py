import tempfile
import zipfile
import base64
import os
import shutil
from lxml import etree

from src.services.custom_llm.services.proccess_images import summary_image_using_llm
import uuid


class ProcessImage:
    already_process_image = dict()

    @classmethod
    def save_cache(cls, image_base64, result):
        uuid_key = uuid.uuid5(uuid.NAMESPACE_DNS, image_base64)
        cls.already_process_image[uuid_key] = result

    @classmethod
    def check_cache(cls, image_base64):
        uuid_key = uuid.uuid5(uuid.NAMESPACE_DNS, image_base64)
        return cls.already_process_image.get(uuid_key, None)

    def __init__(self):
        self.image_collection = dict()

    def convert_docx_images_to_base64(
        self,
        docx_path: str,
        output_docx_path: str,
        is_process_summary: bool,
    ) -> tuple[str, dict]:
        """Convert DOCX images to base64."""
        namespaces = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",  # NOSONAR
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",  # NOSONAR
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",  # NOSONAR
        }

        image_collection = dict()

        def get_image_name(image_collection, image_base64: str):
            # Check if we've already processed this image
            if cached_result := self.check_cache(image_base64):
                return cached_result

            # Use the LLM to check if image is an icon and get summary
            is_icon, summary = summary_image_using_llm(image_base64, is_process_summary)

            # If it's an icon, we'll cache the result directly
            if is_icon:
                result = summary
            else:
                # Instead of looping every time, use next with a generator
                result = next((k for k, v in image_collection.items() if v == image_base64), None)

                # If the image does not exist, create a new entry
                if not result:
                    result = f"<base64>Image_{len(image_collection)}</base64>"
                    image_collection[result] = image_base64

            # Cache the result to skip re-processing in future calls
            self.save_cache(image_base64, result)
            return result

        with tempfile.TemporaryDirectory() as temp_dir:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with zipfile.ZipFile(docx_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            rels_path = os.path.join(temp_dir, "word", "_rels", "document.xml.rels")
            rels_tree = etree.parse(rels_path)
            rels_root = rels_tree.getroot()
            rels_ns = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}  # NOSONAR
            rel_dict = {}
            for rel in rels_root.findall("pr:Relationship", namespaces=rels_ns):
                rId = rel.get("Id")
                target = rel.get("Target")
                rel_dict[rId] = target

            doc_xml_path = os.path.join(temp_dir, "word", "document.xml")
            doc_tree = etree.parse(doc_xml_path)
            doc_root = doc_tree.getroot()

            drawing_elements = doc_root.xpath("//w:drawing", namespaces=namespaces)
            for drawing in drawing_elements:
                blip = drawing.find(".//a:blip", namespaces=namespaces)
                if blip is not None:
                    rId = blip.get("{" + namespaces["r"] + "}embed")
                    if rId and rId in rel_dict:
                        image_rel_path = rel_dict[rId]
                        image_path = os.path.join(temp_dir, "word", image_rel_path)
                        if os.path.exists(image_path):
                            with open(image_path, "rb") as img_file:
                                image_data = img_file.read()
                            b64_str = base64.b64encode(image_data).decode("utf-8")
                            new_t = etree.Element("{" + namespaces["w"] + "}t")
                            new_t.text = get_image_name(image_collection, b64_str)
                            parent = drawing.getparent()
                            index = parent.index(drawing)
                            parent.remove(drawing)
                            parent.insert(index, new_t)

            doc_tree.write(doc_xml_path, xml_declaration=True, encoding="utf-8", standalone="yes")

            # **Tạo thư mục nếu chưa tồn tại**
            output_folder = os.path.dirname(output_docx_path)
            os.makedirs(output_folder, exist_ok=True)

            with zipfile.ZipFile(output_docx_path, "w", zipfile.ZIP_DEFLATED) as docx_zip:
                for foldername, subfolders, filenames in os.walk(temp_dir):
                    for filename in filenames:
                        file_path = os.path.join(foldername, filename)
                        arcname = os.path.relpath(file_path, temp_dir)
                        docx_zip.write(file_path, arcname)

        return output_docx_path, image_collection
