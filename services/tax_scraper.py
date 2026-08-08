import requests
from bs4 import BeautifulSoup
from utils.logger import app_logger
import urllib3
import os

# Suppress insecure request warnings for government sites
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TaxScraper:
    @staticmethod
    def fetch_dues(property_tax_no: str) -> dict:
        url = "https://tnurbanepay.tn.gov.in/PT_CPPaymentDetails.aspx"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Origin': 'https://tnurbanepay.tn.gov.in',
            'Referer': 'https://tnurbanepay.tn.gov.in/PT_CPPaymentDetails.aspx',
            'Connection': 'keep-alive'
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        try:
            app_logger.info(f"🔍 DEBUG: Starting dynamic tax fetch for {property_tax_no}...")
            
            # 1. GET request
            res = session.get(url, verify=False, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 👇 NEW: Dynamically build the payload by scraping ALL input fields
            payload = {}
            for input_tag in soup.find_all("input"):
                name = input_tag.get("name")
                if not name:
                    continue
                    
                type_ = input_tag.get("type", "").lower()
                
                # Do not include other submit/image buttons we aren't clicking
                if type_ in ["submit", "image", "button"]:
                    continue
                    
                # Do not include radio buttons unless we explicitly set them below
                if type_ in ["radio", "checkbox"]:
                    continue
                    
                value = input_tag.get("value", "")
                payload[name] = value
                
            # 2. Inject our specific search parameters
            payload['ctl00$PageContent$rdbulb'] = '0' 
            payload['ctl00$PageContent$txtRefNumber'] = property_tax_no 
            payload['ctl00$PageContent$btnGetDetails'] = 'Search' 
            
            # Ensure standard ASP.NET event targets are present
            payload.setdefault('__EVENTTARGET', '')
            payload.setdefault('__EVENTARGUMENT', '')
            payload.setdefault('__LASTFOCUS', '')
            
            app_logger.info(f"🔍 DEBUG: Submitting POST with {len(payload)} dynamic keys.")
            
            # 3. Submit POST
            post_res = session.post(url, data=payload, verify=False, timeout=15)
            
            # Save debug response
            debug_filepath = os.path.join(os.getcwd(), "debug_tax_response.html")
            with open(debug_filepath, "w", encoding="utf-8") as f:
                f.write(post_res.text)
            
            post_soup = BeautifulSoup(post_res.text, 'html.parser')
            
            # 4. Check if it still crashed to DefaultError.aspx
            if "DefaultError.aspx" in post_res.url or "Your Request could not be processed" in post_res.text:
                return {"error": "❌ The TN Urban portal is rejecting automated requests. Try the manual link instead."}
            
            # 5. Parse the response for Errors
            error_lbl = post_soup.find('span', id='PageContent_lblmsg')
            if error_lbl and error_lbl.text.strip():
                return {"error": f"Portal Message: {error_lbl.text.strip()}"}
                
            # ... (keep everything above Step 6 exactly the same) ...

            # 6. Extract the Data
            owner_name = post_soup.find('span', id='PageContent_alblOwner')
            payable_amt = post_soup.find('span', id='PageContent_lblpayamt')
            balance_amt = post_soup.find('span', id='PageContent_lbl_balanceamt_view')
            
            # Extracting extra property details
            door_no = post_soup.find('span', id='PageContent_alblDoorNo')
            street = post_soup.find('span', id='PageContent_alblStreet1')
            city = post_soup.find('span', id='PageContent_alborganization')
            pincode = post_soup.find('span', id='PageContent_alblPincode')
            
            usage = post_soup.find('span', id='PageContent_lblusage')
            area = post_soup.find('span', id='PageContent_Label21')
            half_yearly_tax = post_soup.find('span', id='PageContent_albl_halfyeartax')
            
           # 👇 NEW: Extract and format the Payment Table with Penalties & Incentives
            dues_breakdown = ""
            payment_table = post_soup.find('table', id='PageContent_gvpayment')
            
            if payment_table:
                rows = payment_table.find_all('tr')
                dues_list = []
                
                # Skip the first row (headers)
                for row in rows[1:]:
                    cols = row.find_all('td')
                    
                    # Data rows have 12 columns. Ensure we have at least 11 to get the incentive.
                    if len(cols) >= 11:
                        period = cols[1].text.strip()
                        
                        # Skip the bottom footer row which says "Total"
                        if period.lower() == 'total' or period == '':
                            continue
                            
                        # Index 8 is "Total Balance Amount"
                        # Index 9 is "Delay Penalty"
                        # Index 10 is "Incentive"
                        amount = cols[8].text.strip() 
                        penalty = cols[9].text.strip()
                        incentive = cols[10].text.strip()
                        
                        line = f"• `{period.ljust(18)}` : ₹{amount}"
                        
                        # Build the extra details string if there's a penalty or incentive
                        extras = []
                        if penalty and penalty not in ['0', '0.00', '']:
                            extras.append(f"+₹{penalty} penalty")
                        if incentive and incentive not in ['0', '0.00', '']:
                            extras.append(f"-₹{incentive} incentive")
                            
                        if extras:
                            line += f" _({', '.join(extras)})_"
                            
                        dues_list.append(line)
                
                if dues_list:
                    # Join the list and wrap it in nice formatting
                    dues_breakdown = "🧾 *Pending Periods Breakdown:*\n" + "\n".join(dues_list) + "\n━━━━━━━━━━━━━━━━━━\n"
            if owner_name and owner_name.text.strip():
                # Clean up the address string
                name_str = owner_name.text.strip()
                address_parts = [
                    door_no.text.strip() if door_no else '',
                    street.text.strip() if street else '',
                    city.text.strip() if city else ''
                ]
                address_str = ", ".join([p for p in address_parts if p])
                if pincode and pincode.text.strip():
                    address_str += f" - {pincode.text.strip()}"
                
                # Format the final Telegram message
                details = (
                    f"👤 *Owner:* {name_str}\n"
                    f"🏠 *Address:* {address_str}\n"
                    f"🏢 *Usage:* {usage.text.strip() if usage else 'N/A'} ({area.text.strip() if area else '0'} Sq.ft)\n"
                    f"📅 *Half Yearly Tax:* ₹{half_yearly_tax.text.strip() if half_yearly_tax else '0.00'}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{dues_breakdown}"  # 👈 Injects the table breakdown here!
                    f"💰 *Balance Amount:* ₹{balance_amt.text.strip() if balance_amt else '0.00'}\n"
                    f"🔴 *Total Payable:* ₹{payable_amt.text.strip() if payable_amt else '0.00'}\n\n"
                    f"[🔗 Click here to pay online]({url})"
                )
                return {"success": True, "details": details}
            else:
                return {"error": "❌ Invalid Assessment Number or no records found."}
                
        except Exception as e:
            app_logger.error(f"Tax scraper failed: {e}", exc_info=True)
            return {"error": "An error occurred while connecting to the portal."}