import os
import re
import pytesseract
import io
from pdf2image import convert_from_bytes
from thefuzz import fuzz
from utils.logger import app_logger

os.environ["OMP_THREAD_LIMIT"] = "1"
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

class OCRVerifier:
    @staticmethod
    def verify_sale_deed(file_data: bytes, expected_flat: str, expected_owner: str, expected_parking: str, expected_reg_no: str = "") -> dict:
        """Runs OCR and actively extracts data for CGEWHO Possession Letters, No Dues, and Sale Deeds."""
        try:
            images = convert_from_bytes(file_data, size=(1600, None), poppler_path="/usr/bin")
            
            ocr_text = ""
            for img in images:
                ocr_text += pytesseract.image_to_string(img.convert('L'))
            
            ocr_text_clean = " ".join(ocr_text.split()).upper()
            app_logger.info(f"RAW OCR TEXT FOR FLAT {expected_flat}: {ocr_text_clean}")
            
            result = {
                "expected_flat": expected_flat, "extracted_flat": "Not Found",
                "expected_parking_lot": expected_parking or "None", "extracted_parking_lot": "Not Found",
                "expected_buyer": expected_owner, "extracted_buyer": "Not Found",
                "expected_reg_no": expected_reg_no or "None", "extracted_reg_no": "Not Found",
                "buyer_match_score": 0, "error": None, "raw_text": ocr_text_clean,
                "detected_format": "unknown" 
            }

            # ==========================================
            # PART 1: EXTRACT DATA & DETECT FORMAT
            # ==========================================
            
            # 1. Base markers required on ALL documents
            base_markers = ["CGEWHO"]
            
            # 2. Format identifiers (Added Sale Deed)
            has_old_format = "527/2024" in ocr_text_clean or "POSSESSION" in ocr_text_clean
            has_new_format = "CM_POSS" in ocr_text_clean or "HANDING" in ocr_text_clean
            has_nodues_format = "NO DUES" in ocr_text_clean or "ELECTRICITY" in ocr_text_clean
            has_saledeed_format = "DEED OF SALE" in ocr_text_clean or "SALE DEED" in ocr_text_clean
            
            if has_new_format:
                result["detected_format"] = "new"
            elif has_nodues_format:
                result["detected_format"] = "nodues"
            elif has_saledeed_format:
                result["detected_format"] = "saledeed"
            elif has_old_format:
                result["detected_format"] = "old"

            missing_markers = [m for m in base_markers if m not in ocr_text_clean]
            
            # 3. Dynamic Signature Check
            signature_markers = ["VIGNESH", "SIGNATORY", "AUTHORISED", "FOR CGEWHO"]
            if not any(sig in ocr_text_clean for sig in signature_markers):
                missing_markers.append("Authorized Signature (VIGNESH, SIGNATORY, or FOR CGEWHO)")

            if not (has_old_format or has_new_format or has_nodues_format or has_saledeed_format):
                missing_markers.append("Format identifiers missing (Expected 'POSSESSION', 'NO DUES', or 'DEED OF SALE')")

            # A. Extract Registration Number (Hunts for CMA, CMB, CMC, CMD with optional spaces or hyphens)
            cmd_match = re.search(r"(CM[A-D][\s\-]*\d+)", ocr_text_clean)
            reg_match = re.search(r"REGN\s*NO[\s\;\:]*([A-Z0-9]+)", ocr_text_clean)
            
            if cmd_match:
                # Extracts the match and strips out any spaces or hyphens for a clean ERP comparison
                result["extracted_reg_no"] = cmd_match.group(1).replace(" ", "").replace("-", "").strip()
            elif reg_match:
                result["extracted_reg_no"] = reg_match.group(1).strip()
            elif expected_reg_no and expected_reg_no.replace(" ", "") in ocr_text_clean.replace(" ", ""):
                result["extracted_reg_no"] = expected_reg_no

            # B. Name Match & Active Extraction
            name_score = fuzz.partial_ratio(expected_owner.upper(), ocr_text_clean)
            result["buyer_match_score"] = name_score
            
            nodues_name_match = re.search(r"CERTIFY\s+THAT\s+(?:SH|SMT|MR|MRS|MS|SHRI)?\.?\s*([A-Z\s\.]+?)\s*\(", ocr_text_clean)
            poss_name_match = re.search(r"CERTIFIED\s+THAT\s+([A-Z\s\.]+?)\s+REGISTERED", ocr_text_clean)
            saledeed_name_match = re.search(r"BETWEEN\s+CGEWHO.*?AND\s+([A-Z\s\.]+?)\s+HEREINAFTER", ocr_text_clean)
            
            if nodues_name_match:
                result["extracted_buyer"] = nodues_name_match.group(1).strip()
            elif poss_name_match:
                result["extracted_buyer"] = poss_name_match.group(1).strip()
            elif saledeed_name_match:
                result["extracted_buyer"] = saledeed_name_match.group(1).strip()
            elif name_score >= 80: 
                result["extracted_buyer"] = expected_owner

           # C. Parking Match (Enhanced for OCR artifact gaps before NIL and strict "NO" check)
            if re.search(r"PARKING.*?NIL", ocr_text_clean):
                result["extracted_parking_lot"] = "NIL"
            elif expected_parking and expected_parking.upper() != "NIL":
                core_parking = "-".join(expected_parking.split('-')[-2:]) if len(expected_parking.split('-')) >= 2 else expected_parking
                parking_digits = "".join(re.findall(r'\d+', expected_parking))
                
                if core_parking in ocr_text_clean or core_parking.replace("-", "") in ocr_text_clean.replace(" ", ""):
                    result["extracted_parking_lot"] = expected_parking
                # Bypass OCR table destruction on Sale Deeds by hunting just the parking digits
                elif has_saledeed_format and parking_digits and parking_digits in ocr_text_clean:
                    result["extracted_parking_lot"] = expected_parking
                else:
                    # Strict check for "PARKING NO" to avoid grabbing random text like "ALLOTTED"
                    park_match = re.search(r"PARKING\s*NO[^\:]*[\:\.]*\s*([A-Z0-9\-]{3,10})", ocr_text_clean)
                    if park_match and "LOW" not in park_match.group(1): 
                        result["extracted_parking_lot"] = park_match.group(1)
            else:
                # Strict check for "PARKING NO" to avoid grabbing random text like "ALLOTTED"
                park_match = re.search(r"PARKING\s*NO[^\:]*[\:\.]*\s*([A-Z0-9\-]{3,10})", ocr_text_clean)
                if park_match and "LOW" not in park_match.group(1): 
                    result["extracted_parking_lot"] = park_match.group(1)
            
            if result["extracted_parking_lot"] == "Not Found" and not expected_parking:
                result["extracted_parking_lot"] = "None"

            # D. Flat Match (Enhanced to survive Sale Deed table chaos and high floors)
            expected_digits = "".join(re.findall(r'\d+', expected_flat))
            core_flat = expected_flat.split('-')[-1]
            block_flat = expected_flat.split('-')[0]
            
            nodues_flat_match = re.search(r"UNIT\s*NO[^\d]*(\d+)\s*IN\s*BLOCK\s*NO[^\w]*([A-Z0-9\-]+)", ocr_text_clean)
            saledeed_flat_match = re.search(r"DWELLING\s*UNIT[^\d]*(\d+)", ocr_text_clean)
            
            # 👇 Tailored strictly for a 10-story building (plus common OCR typos like FIOOF)
            flat_line_match = re.search(r"FLAT\s*NO.*?(?:TENTH|NINTH|EIGHTH|SEVENTH|SIXTH|FIFTH|FOURTH|THIRD|SECOND|FIRST|GROUND|FIOOF)", ocr_text_clean)
            
            clean_ocr_no_hyphens = ocr_text_clean.replace(" ", "").replace("-", "")

            if nodues_flat_match:
                ext_block = nodues_flat_match.group(2).replace("-", "").replace(" ", "")
                ext_flat = nodues_flat_match.group(1)
                result["extracted_flat"] = f"{ext_block}-{ext_flat}"
            
            # Sale Deed bypass 1: Finds the core digits if they exist
            elif has_saledeed_format and saledeed_flat_match and saledeed_flat_match.group(1) == core_flat:
                result["extracted_flat"] = expected_flat
                
            elif flat_line_match:
                extracted_digits = "".join(re.findall(r'\d+', flat_line_match.group(0)))
                if expected_digits in extracted_digits or core_flat in extracted_digits:
                    result["extracted_flat"] = expected_flat
            elif core_flat in clean_ocr_no_hyphens and (block_flat in clean_ocr_no_hyphens or block_flat.replace("T", "") in clean_ocr_no_hyphens):
                result["extracted_flat"] = expected_flat 

            # 👇 THE ULTIMATE FALLBACK: If OCR completely erased the flat digits, trust a perfect Parking + Block match!
            if result["extracted_flat"] == "Not Found" and has_saledeed_format:
                if expected_parking and expected_parking not in ["None", "NIL", ""]:
                    core_expected_park = "-".join(expected_parking.split('-')[-2:]) if "-" in expected_parking else expected_parking
                    # If the unique parking slot (e.g. CS-2) is found on the page...
                    if core_expected_park in result["extracted_parking_lot"] or core_expected_park in ocr_text_clean:
                        # ...and the Block (e.g. TB1) is also on the page, we approve the flat!
                        if block_flat in clean_ocr_no_hyphens or block_flat.replace("T", "") in clean_ocr_no_hyphens:
                            result["extracted_flat"] = expected_flat

            # ==========================================
            # 🔍 DEBUG LOGGING: Print Extracted Data
            # ==========================================
            app_logger.info(
                f"🔍 OCR EXTRACTION RESULTS FOR [{expected_flat}]: "
                f"Format='{result['detected_format']}' | "
                f"Extracted Buyer='{result['extracted_buyer']}' (Score: {result['buyer_match_score']}) | "
                f"Extracted Flat='{result['extracted_flat']}' | "
                f"Extracted Reg No='{result['extracted_reg_no']}' | "
                f"Extracted Parking='{result['extracted_parking_lot']}'"
            )

            # ==========================================
            # PART 2: APPLY GATEKEEPER RULES
            # ==========================================
            
            if len(missing_markers) > 0:
                app_logger.warning(f"OCR Reject [{expected_flat}]: Missing markers: {missing_markers}")
                result["error"] = f"Verification Failed: Missing mandatory document markers or signatures: {missing_markers}"
                return result

            if result["extracted_flat"] == "Not Found":
                app_logger.warning(f"OCR Reject [{expected_flat}]: Flat missing.")
                result["error"] = "Verification Failed: Could not detect the Flat Number."
                return result
            
            extracted_core = result["extracted_flat"].split("-")[-1] if "-" in result["extracted_flat"] else result["extracted_flat"]
            if core_flat not in extracted_core:
                app_logger.warning(f"OCR Reject [{expected_flat}]: Flat mismatch. Found {result['extracted_flat']}")
                result["error"] = f"Verification Failed: Document belongs to Flat {result['extracted_flat']}, not {expected_flat}."
                return result

            if expected_reg_no and result["extracted_reg_no"] != "Not Found":
                if fuzz.ratio(expected_reg_no.upper().replace(" ", ""), result["extracted_reg_no"].replace(" ", "")) < 80:
                    app_logger.warning(f"OCR Reject [{expected_flat}]: Reg No mismatch.")
                    result["error"] = "Verification Failed: Registration Number mismatch."
                    return result
                
            if name_score < 40:
                app_logger.warning(f"OCR Reject [{expected_flat}]: Name missing.")
                result["error"] = "Verification Failed: Owner Name mismatch."
                return result

            return result

        except Exception as e:
            app_logger.error(f"OCR Verification failed: {str(e)}")
            return {"error": str(e), "detected_format": "unknown"}

    @classmethod
    def process_full_verification(cls, erp_client, file_ids, flat_number: str, update_status: bool = True) -> dict:
        """Shared logic to download, compress, merge, OCR, and upload to ERPNext."""
        import os, requests, re, io
        from datetime import datetime
        from difflib import SequenceMatcher
        from pypdf import PdfReader, PdfWriter
        from utils.logger import app_logger

        try:
            bot_token = os.getenv("SOCIETY_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")

            def download_file(f_id):
                file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={f_id}"
                file_path = requests.get(file_info_url).json().get("result", {}).get("file_path")
                if not file_path: return None
                
                raw_data = requests.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}").content
                
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    from PIL import Image
                    image = Image.open(io.BytesIO(raw_data)).convert("RGB")
                    pdf_bytes = io.BytesIO()
                    image.save(pdf_bytes, format="PDF")
                    return pdf_bytes.getvalue()
                    
                return raw_data

            writer = PdfWriter()
            is_single_page = False

            if isinstance(file_ids, list):
                for f_id in file_ids:
                    f_data = download_file(f_id)
                    if not f_data: return {"success": False, "error": "Failed to fetch file from Telegram."}
                    reader = PdfReader(io.BytesIO(f_data))
                    writer.add_page(reader.pages[0])
                    writer.pages[-1].compress_content_streams()
                
                output_stream = io.BytesIO()
                writer.write(output_stream)
                file_data = output_stream.getvalue()

            else:
                original_file_data = download_file(file_ids)
                if not original_file_data: return {"success": False, "error": "Failed to fetch file from Telegram."}
                
                try:
                    reader = PdfReader(io.BytesIO(original_file_data))
                    if len(reader.pages) == 1:
                        is_single_page = True
                    
                    for i in range(min(len(reader.pages), 2)):
                        writer.add_page(reader.pages[i])
                        writer.pages[i].compress_content_streams()
                        
                    output_stream = io.BytesIO()
                    writer.write(output_stream)
                    file_data = output_stream.getvalue()
                except Exception as pdf_e:
                    return {"success": False, "error": "Could not read the PDF/Image."}
            
            profile = erp_client.get_resident_profile(flat_number)
            if not profile or not profile.owner_name:
                return {"success": False, "error": f"No valid owner record for Flat {flat_number}."}
                
            expected_owner = profile.owner_name
            expected_parking = profile.parking_slot or ""
            expected_reg = getattr(profile, 'CGEWHO_reg_no', '') or ''
            
            ocr_result = cls.verify_sale_deed(file_data, flat_number, expected_owner, expected_parking, expected_reg)
            
            if ocr_result.get("error"):
                # If a Sale Deed fails (e.g. missing Name on Page 1), it falls here and triggers the Page 2 request!
                if is_single_page and ocr_result.get("detected_format") not in ["new", "nodues"]:
                    return {"success": False, "status": "needs_page_2", "file_id": file_ids}
                return {"success": False, "error": ocr_result["error"]}
                
            def clean_name(name): return re.sub(r'[^A-Z]', '', str(name).upper()) if name else ""
            score = int(SequenceMatcher(None, clean_name(expected_owner), clean_name(ocr_result.get('extracted_buyer', ''))).ratio() * 100)
            
            table = (
                f"\n\n📊 *Data Comparison:*\n"
                f"🏢 *Flat No:* `{flat_number}` (ERP) 🆚 `{ocr_result.get('extracted_flat')}` (PDF)\n"
                f"🚗 *Parking:* `{expected_parking}` (ERP) 🆚 `{ocr_result.get('extracted_parking_lot')}` (PDF)\n"
                f"👤 *Buyer:* `{expected_owner}` (ERP) 🆚 `{ocr_result.get('extracted_buyer')}` (PDF)\n"
                f"🆔 *Regn No:* `{expected_reg}` (ERP) 🆚 `{ocr_result.get('extracted_reg_no')}` (PDF)\n"
                f"💯 *Name Score:* {score}%"
            )
            
            if score < 80:
                return {"success": False, "status": "Failed", "error": f"Document data mismatch. {table}", "score": score, "table": table}
                
            api_base = getattr(erp_client, "base_client", erp_client)
            upload_res = api_base.upload_file(
                doctype="Owners", docname=profile.owner_id, 
                file_name=f"PossessionLetter_{flat_number}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf", 
                file_data=file_data, mime_type="application/pdf"
            )
            
            if isinstance(upload_res, dict) and upload_res.get("success"):
                update_data = {"sale_deed": upload_res.get("file_url")}
                if update_status: update_data["registration_status"] = "Verified by Bot"
                api_base.update_document("Owners", profile.owner_id, update_data)
                
            return {"success": True, "status": "Verified by Bot", "table": table, "score": score, "is_rented": profile.is_rented}

        except Exception as e:
            app_logger.error(f"OCR Full Verification Crash: {str(e)}")
            return {"success": False, "error": f"System error: {str(e)}"}