import requests
from utils.logger import app_logger

class KeyboardBuilder:

    MAIN_MENU_BACK = [{"text": "🔙 Main Menu", "callback_data": "/menu"}]
    @staticmethod
    def _fetch_options(doctype: str, fieldname: str, fallback: list) -> list:
        from utils.logger import app_logger
        import requests
        
        try:
            from api.erp import ERPClient
            erp = ERPClient()
            
            # Clean the base URL by removing /api/resource
            clean_domain = erp.base_url.split("/api/")[0] 
            
            url = f"{clean_domain}/api/method/frappe.desk.form.load.getdoctype"
            params = {"doctype": doctype}
            
            resp = requests.get(url, headers=erp.headers, params=params, timeout=3)
            
            if resp.status_code == 200:
                docs = resp.json().get("docs", [])
                
                for doc in docs:
                    # 👇 NEW: Look inside the nested "fields" array of the main DocType object
                    fields = doc.get("fields", [])
                    
                    for field in fields:
                        if field.get("fieldname") == fieldname:
                            options_str = field.get("options")
                            
                            if options_str:
                                options = [opt.strip() for opt in options_str.split("\n") if opt.strip()]
                                if options:
                                    app_logger.debug(f"✅ DYNAMIC KEYBOARD: Fetched {len(options)} options for {doctype}.{fieldname} via Desk API.")
                                    return options
                                    
                app_logger.warning(f"⚠️ DYNAMIC KEYBOARD: Field '{fieldname}' not found in '{doctype}'. Using fallback.")
            else:
                app_logger.warning(f"⚠️ DYNAMIC KEYBOARD: Desk API returned HTTP {resp.status_code} for {doctype}. Using fallback.")
            
        except Exception as e:
            app_logger.error(f"❌ DYNAMIC KEYBOARD: API fetch crashed for {doctype}.{fieldname} - {e}. Using fallback.")
            
        return fallback
    # ==========================================
    # 🔄 DYNAMICALLY REWRITTEN MENUS
    # ==========================================
    
    @staticmethod
    def maintenance_categories() -> list:
        options = KeyboardBuilder._fetch_options("Maintenance Ticket", "category", ["Handing Over", "Defects Rectification", "Other"])
        return KeyboardBuilder.dynamic_filter_grid(options, "/cat_")

    @staticmethod
    def walkin_purpose() -> list:
        options = KeyboardBuilder._fetch_options("Visitor Log", "purpose", ["Delivery", "Cab", "Service", "Guest"])
        return KeyboardBuilder.dynamic_filter_grid(options, "wpurp_")

    @staticmethod
    def staff_categories() -> list:
        options = KeyboardBuilder._fetch_options("Domestic Staff", "role", ["Maid", "Cook", "Driver", "Nanny", "Plumber", "Electrician"])
        return KeyboardBuilder.dynamic_filter_grid(options, "/st_cat_", back_button=("🔙 Back to Staff", "/staff"))

    @staticmethod
    def family_relations() -> list:
        options = KeyboardBuilder._fetch_options("Family Members", "relationship", ["Spouse", "Child", "Parent", "Sibling", "Other"])
        return KeyboardBuilder.dynamic_filter_grid(options, "/fam_rel_", back_button=("❌ Cancel", "/cancel"))

    @staticmethod
    def tenant_relationship_grid() -> list:
        options = KeyboardBuilder._fetch_options("Tenants", "tenant_relationship", ["Tenant", "Caretaker", "Company Lease", "Guest House"])
        return KeyboardBuilder.dynamic_filter_grid(options, "/rel_", back_button=("❌ Cancel & Exit", "/cancel"))

    @staticmethod
    def wp_work_type_grid() -> list:
        options = KeyboardBuilder._fetch_options("Work Permit", "work_type", ["Interior", "Civil", "Carpentry", "Painting", "Other"])
        return KeyboardBuilder.dynamic_filter_grid(options, "/wp_type_", back_button=("❌ Cancel", "/cancel"))

    @staticmethod
    def viol_block_grid() -> list:
        # Note: If 'target_block' is a Link field instead of Select, this will use the fallback. 
        options = KeyboardBuilder._fetch_options("Work Permit Violation", "target_block", ["TA1", "TA2", "TB1", "TB2", "TC1", "TC2", "TC3", "TD1", "TD2", "TD3"])
        return KeyboardBuilder.dynamic_filter_grid(options, "/vblock_", back_button=("🔙 Cancel", "/menu"))

    @staticmethod
    def viol_type_grid() -> list:
        options = KeyboardBuilder._fetch_options("Work Permit Violation", "violation_type", ["Debris", "Noise", "Parking", "Damage", "Other"])
        return KeyboardBuilder.dynamic_filter_grid(options, "/vtype_", back_button=("🔙 Cancel", "/menu"))

    @staticmethod
    def admin_ticket_status_grid() -> list:
        # Fetch the options dynamically as you were doing before
        options = KeyboardBuilder._fetch_options("Maintenance Ticket", "status", ["Open", "Assigned", "Resolved", "Closed"])
        grid = KeyboardBuilder.dynamic_filter_grid(options, "/adm_tstat_", back_button=("🔙 Admin Menu", "/menu"))
        
        # 👇 NEW: Insert the PDF download button at the very top (index 0)
        grid.insert(0, [{"text": "📥 Download Open Tickets (PDF)", "callback_data": "/adm_tkt_pdf"}])
        
        return grid

    @staticmethod
    def admin_ticket_category_grid(status: str) -> list:
        options = KeyboardBuilder._fetch_options("Maintenance Ticket", "category", ["Handing Over", "Defects Rectification", "Other Issues"])
        return KeyboardBuilder.dynamic_filter_grid(options, f"/adm_tcat_{status}_", back_button=("🔙 Back to Status", "/admin_tickets"))

    @staticmethod
    def admin_wp_status_filters() -> list:
        options = KeyboardBuilder._fetch_options("Work Permit", "status", ["Pending", "Approved", "Rejected", "Completed"])
        return KeyboardBuilder.dynamic_filter_grid(options, "/adm_wpsel_", back_button=("🔙 Admin Menu", "/menu"))


    # ==========================================
    # 📌 PRESERVED STATIC MENUS (No changes)
    # ==========================================
    
    @staticmethod
    def back_to_menu() -> list:
        return [[{"text": "🔙 Main Menu", "callback_data": "/menu"}]]

    @staticmethod
    def cancel_operation() -> list:
        return [[{"text": "❌ Cancel", "callback_data": "/cancel"}]]
        
    @staticmethod
    def main_menu(role: str) -> list:
        menu = [
            [{"text": "🎫 Gate Pass", "callback_data": "/visitors"}, {"text": "🛠️ Maintenance", "callback_data": "/raise_ticket"}],
            [{"text": "👨‍👩‍👧‍👦 Family", "callback_data": "/family"}, {"text": "🧹 Staff", "callback_data": "/staff"}],
            [{"text": "📋 Notices", "callback_data": "/notices"}, {"text": "💵 Dues", "callback_data": "/dues"}],
            [{"text": "🎾 Book Facility", "callback_data": "/book_facility"}, {"text": "👤 Profile", "callback_data": "/profile"}]
        ]
        if role == "Owner":
            menu.append([{"text": "🏢 Tenant Management", "callback_data": "/tenant"}])
        return menu

    @staticmethod
    def walkin_approval(log_id: str, chat_id: str, flat: str) -> list:
        return [
            [{"text": "✅ Approve", "callback_data": f"w_app_{log_id}_{chat_id}_{flat}"}, {"text": "❌ Deny", "callback_data": f"w_den_{log_id}_{chat_id}_{flat}"}]
        ]
        
    @staticmethod
    def scanner_loop() -> list:
        return [[{"text": "📷 Scan Next Pass", "web_app": {"url": "https://kvc3.railwayofficersclub.in/scanner"}}]]

    @staticmethod
    def resident_grid(is_owner: bool, is_rented: bool = False, is_aoa_member: bool = False) -> list:
        grid = []
        if not (is_owner and is_rented):
            grid.extend([
                [{"text": "🎫 Pre-Approve Visitor", "callback_data": "/invite"}, {"text": "📋 Visitor History", "callback_data": "/history"}],
                [{"text": "🛠️ Raise Ticket", "callback_data": "/raise_ticket"}, {"text": "🔍 My Tickets", "callback_data": "/my_tickets"}],
                [{"text": "🚗 My Vehicles", "callback_data": "/my_vehicles"}],
                [{"text": "👨‍👩‍👧‍👦 Family", "callback_data": "/family"}, {"text": "🧹 Staff", "callback_data": "/staff"}]
            ])
            
        grid.extend([
            [{"text": "📋 Notice Board", "callback_data": "/notices"}, {"text": "🏛️ Book Facility", "callback_data": "/book_facility"}],
            [{"text": "🐾 Pet Details", "callback_data": "/pets"}, {"text": "📊 Check Dues", "callback_data": "/dues"}],
            [{"text": "🚨 Report Violation", "callback_data": "/report_violation"}, {"text": "📋 Reported Violations", "callback_data": "/my_violations"}]
        ])
        
        if is_owner:
            grid.extend([
                [{"text": "👤 Profile", "callback_data": "/profile"}, {"text": "🏠 Tenant", "callback_data": "/tenant"}],
                [{"text": "👷 Work Permit", "callback_data": "/work_permit"}]
            ])
        else:
            grid.append([{"text": "👤 Profile", "callback_data": "/profile"}])
            
        # The AoA Monitor button has been successfully extracted from here!
            
        grid.append([{"text": "🚪 Logout", "callback_data": "/logout"}])
        return grid

    @staticmethod
    def guard_inline_keyboard() -> list:
        return [
            [{"text": "📷 Scan QR Pass", "web_app": {"url": "https://kvc3.railwayofficersclub.in/scanner"}}],
            [{"text": "🚶 Walk-in Entry", "callback_data": "/guard_walkin"}],
            [{"text": "🚗 Vehicle Lookup", "callback_data": "/vehicle_lookup"}, {"text": "📦 Log Parcel", "callback_data": "/log_parcel"}],
            [{"text": "🚨 Emergency SOS", "callback_data": "/sos_status"}]
        ]

    @staticmethod
    def staff_list_menu(staff_list: list) -> list:
        keyboard = []
        for staff in staff_list:
            name = staff.get("staff_name", "Unknown")
            role = staff.get("role", "Staff")
            staff_id = staff.get("name", "")
            
            callback_data = f"/st_view_{staff_id}"
            button_text = f"👤 {name} ({staff_id}) - {role}"
            keyboard.append([{"text": button_text, "callback_data": callback_data}])
            
        keyboard.append([{"text": "➕ Find & Link New Staff", "callback_data": "/st_add"}])
        keyboard.append([{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}])
        return keyboard

    @staticmethod
    def society_staff_list(staff_list, category):
        buttons = []
        for staff in staff_list:
            staff_id = staff.get('name', 'Unknown')
            staff_name = staff.get('staff_name', 'Unknown')
            rating = staff.get('avg_rating', 0)
            
            rating_str = f"⭐ {rating}/5" if rating > 0 else "⭐ New/No Rating"
            button_text = f"{staff_name} ({staff_id}) | {rating_str}" 
            callback_data = f"/st_link_{staff_id}" 
            
            buttons.append([{"text": button_text, "callback_data": callback_data}])
            
        buttons.append([{"text": "🔙 Back", "callback_data": "/st_add"}]) 
        return buttons

    @staticmethod
    def staff_manage_menu(staff_id: str) -> list:
        return [
            [{"text": "⭐ Rate Staff", "callback_data": f"/st_rate_{staff_id}"}, 
             {"text": "💬 Write Review", "callback_data": f"/st_comp_{staff_id}"}],
            [{"text": "❌ Unlink Staff", "callback_data": f"/st_unlink_{staff_id}"}],
            [{"text": "🔙 Back to My Staff", "callback_data": "/staff"}]
        ]

    @staticmethod
    def family_management_menu() -> list:
        menu = [
            [{"text": "➕ Add Family Member", "callback_data": "/fam_add"}]
        ]
        menu.extend(KeyboardBuilder.back_to_menu())
        return menu

    @staticmethod
    def request_contact_keyboard() -> dict:
        return {
            "keyboard": [[{"text": "📞 Share Contact", "request_contact": True}]],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }

    @staticmethod
    def admin_grid() -> list:
        return [
            [{"text": "🎫 View Tickets", "callback_data": "/admin_tickets"}, {"text": "👷 Work Permits", "callback_data": "/admin_wp"}],
            [{"text": "🚨 Violations", "callback_data": "/admin_violations"}, {"text": "👥 Resident Search", "callback_data": "/admin_residents"}],
            [{"text": "📋 Today's Visitors", "callback_data": "/admin_visitors"}, {"text": "📢 Broadcast Notice", "callback_data": "/admin_notice"}],
            [{"text": "🚪 Logout", "callback_data": "/logout"}]
        ]

    @staticmethod
    def registration_role_grid(is_rented: bool) -> list:
        grid = [
            [{"text": "👤 Flat Owner", "callback_data": "/reg_role_Owner"}],
            [{"text": "👨‍👩‍👧‍👦 Family Member", "callback_data": "/reg_role_Family"}]
        ]
        if is_rented:
            grid.insert(1, [{"text": "🏠 Tenant", "callback_data": "/reg_role_Tenant"}])
        return grid

    @staticmethod
    def profile_edit_phone_grid() -> list:
        return [
            [{"text": "🗑️ Clear Phone Number", "callback_data": "/clear_phone"}],
            [{"text": "❌ Cancel", "callback_data": "/profile"}]
        ]

    @staticmethod
    def family_active_menu(members: list, can_manage: bool) -> list:
        keyboard = []
        if can_manage:
            for m in members:
                keyboard.append([{"text": f"❌ Deactivate {m.get('member_name')}", "callback_data": f"/fam_del_{m.get('name')}"}])
            keyboard.append([{"text": "➕ Add Family Member", "callback_data": "/fam_add"}])
            keyboard.append([{"text": "👁️ View Inactive Members", "callback_data": "/fam_inactive"}])
        # 👇 CHANGED TO RESIDENT PORTAL
        keyboard.append([{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}])
        return keyboard

    @staticmethod
    def family_inactive_menu(members: list, can_manage: bool) -> list:
        keyboard = []
        if can_manage:
            for m in members:
                keyboard.append([{"text": f"✅ Reactivate {m.get('member_name')}", "callback_data": f"/fam_react_{m.get('name')}"}])
        keyboard.append([{"text": "🔙 Back to Active Family", "callback_data": "/family"}])
        return keyboard

    @staticmethod
    def visitor_invite_grid(freq_visitors: list) -> list:
        grid = [[{"text": "📦 Quick Delivery (Today)", "callback_data": "/vquick_del"}]]
        row = []
        for v in freq_visitors:
            safe_v = v.replace(" ", "_")[:20] 
            row.append({"text": f"👤 {v}", "callback_data": f"/vfreq_{safe_v}"})
            if len(row) == 2:
                grid.append(row)
                row = []
        if row: grid.append(row)
        # 👇 CHANGED TO RESIDENT PORTAL
        grid.append([{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}])
        return grid

    @staticmethod
    def visitor_date_grid() -> list:
        return [
            [{"text": "📅 Today", "callback_data": "/vdate_today"}, {"text": "📆 Tomorrow", "callback_data": "/vdate_tomorrow"}],
            [{"text": "🗓️ Multi-Day Pass", "callback_data": "/vdate_multi"}],
            # 👇 CHANGED TO RESIDENT PORTAL
            [{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}]
        ]

    @staticmethod
    def visitor_duration_grid() -> list:
        return [
            [{"text": "+ 3 Days", "callback_data": "/vend_3days"}, {"text": "+ 1 Week", "callback_data": "/vend_1week"}], 
            # 👇 CHANGED TO RESIDENT PORTAL
            [{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}]
        ]

    @staticmethod
    def visitor_vehicle_skip_grid() -> list:
        return [
            [{"text": "⏭️ Skip", "callback_data": "/vveh_skip"}], 
            # 👇 CHANGED TO RESIDENT PORTAL
            [{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}]
        ]

    @staticmethod
    def visitor_history_grid(offset: int) -> list:
        btns = [{"text": "⬅️ Previous Week", "callback_data": f"/visitors_{offset + 1}"}]
        if offset > 0: 
            btns.append({"text": "Next Week ➡️", "callback_data": f"/visitors_{offset - 1}" if offset > 1 else "/history"})
        # 👇 CHANGED TO RESIDENT PORTAL
        return [btns, [{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}]]
    @staticmethod
    def tenant_confirmation_grid() -> list:
        return [
            [{"text": "✅ Confirm", "callback_data": "/confirm_tenant"}],
            [{"text": "❌ Cancel", "callback_data": "/cancel"}]
        ]

    @staticmethod
    def tenant_deactivate_confirm_grid() -> list:
        return [
            [{"text": "✅ Yes, Deactivate", "callback_data": "/confirm_deactivate_tenant"}],
            [{"text": "🔙 Cancel", "callback_data": "/tenant"}]
        ]

    @staticmethod
    def maintenance_ticket_success_grid(ticket_id: str) -> list:
        return [
            [{"text": "📎 Add Photo (Max 3)", "callback_data": f"/addfile_{ticket_id}"}],
            # 👇 CHANGED TO RESIDENT PORTAL
            [{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}]
        ]

    @staticmethod
    def maintenance_active_tickets_grid(tickets: list, offset: int, status_filter: str) -> list:
        grid = []
        for i in range(0, len(tickets), 2):
            row = [{"text": f"🎫 {tickets[i]['name']}", "callback_data": f"/view_{tickets[i]['name']}"}]
            if i + 1 < len(tickets):
                row.append({"text": f"🎫 {tickets[i+1]['name']}", "callback_data": f"/view_{tickets[i+1]['name']}"})
            grid.append(row)
        
        grid.append([
            {"text": "🟢 Open", "callback_data": "/my_tickets_0_Open"},
            {"text": "🔴 Closed", "callback_data": "/my_tickets_0_Closed"}
        ])
        
        nav_row = []
        if offset >= 10: nav_row.append({"text": "⬅️ Prev", "callback_data": f"/my_tickets_{offset - 10}_{status_filter}"})
        if len(tickets) == 10: nav_row.append({"text": "Next ➡️", "callback_data": f"/my_tickets_{offset + 10}_{status_filter}"})
        if nav_row: grid.append(nav_row)
        
        # 👇 CHANGED TO RESIDENT PORTAL
        grid.append([{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}])
        return grid
    @staticmethod
    def maintenance_ticket_view_grid(ticket_name: str, is_admin: bool, current_status: str, attachments: list) -> list:
        grid = []
        photo_row = []
        for i, file_doc in enumerate(attachments):
            photo_row.append({"text": f"🖼️ Photo {i+1}", "callback_data": f"/viewfile_{file_doc['name']}"})
            if len(photo_row) == 2:
                grid.append(photo_row)
                photo_row = []
        if photo_row: grid.append(photo_row)
            
        if is_admin:
            grid.append([
                {"text": "🔄 Change Status", "callback_data": f"/admin_stat_{ticket_name}"},
                {"text": "💬 Add Remark", "callback_data": f"/admin_rem_{ticket_name}"}
            ])
            grid.append([{"text": "📸 Add Photos (Max 3)", "callback_data": f"/addfile_{ticket_name}"}])
            grid.append([{"text": "🔙 Back to Ticket Menu", "callback_data": "/admin_tickets"}])
        else:
            if current_status == "Resolved":
                grid.append([{"text": "❌ Not Satisfied? Reopen", "callback_data": f"/reopen_{ticket_name}"}])
            else:
                grid.append([{"text": "✅ Close Ticket", "callback_data": f"/res_close_{ticket_name}"}])
                grid.append([{"text": "💬 Add Comment", "callback_data": f"/res_rem_{ticket_name}"}])
                grid.append([{"text": "📸 Add Photos (Max 3)", "callback_data": f"/addfile_{ticket_name}"}])
            grid.append([{"text": "🔙 Back to Tickets", "callback_data": f"/my_tickets_0_{current_status}"}])
        return grid

    @staticmethod
    def wp_confirm_grid() -> list:
        return [
            [{"text": "✅ Submit", "callback_data": "/confirm_permit"}],
            [{"text": "❌ Cancel", "callback_data": "/cancel"}]
        ]

    @staticmethod
    def viol_permit_grid(active_permits: list, block_prefix: str, show_other_block: bool = True) -> list:
        grid = []
        if active_permits:
            for p in active_permits:
                grid.append([{"text": f"🏠 {p['flat_number']} - {p['work_type'][:15]}", "callback_data": f"/violate_{p['name']}"}])
                
        grid.append([{"text": "❓ Unknown Flat (Block Level)", "callback_data": "/violate_UNKNOWN"}])
        if show_other_block:
            grid.append([{"text": "🏢 Report in Another Block", "callback_data": "/violate_OTHER"}])
        # 👇 CHANGED TO RESIDENT PORTAL
        grid.append([{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}])
        return grid

    @staticmethod
    def viol_skip_photo_grid() -> list:
        return [[{"text": "Skip / Submit", "callback_data": "/skip_photo"}]]

    @staticmethod
    def admin_ticket_list_grid(tickets: list, status: str) -> list:
        grid = []
        for i in range(0, len(tickets), 2):
            row = [{"text": f"🎫 {tickets[i]['name']}", "callback_data": f"/view_{tickets[i]['name']}"}]
            if i + 1 < len(tickets):
                row.append({"text": f"🎫 {tickets[i+1]['name']}", "callback_data": f"/view_{tickets[i+1]['name']}"})
            grid.append(row)
        grid.append([{"text": "🔙 Back to Categories", "callback_data": f"/adm_tstat_{status}"}])
        return grid

    @staticmethod
    def admin_ticket_action_grid(ticket_id: str) -> list:
        return [
            [{"text": "🟢 Open", "callback_data": f"/admin_set_{ticket_id}_Open"}, {"text": "🟡 Assigned", "callback_data": f"/admin_set_{ticket_id}_Assigned"}],
            [{"text": "🔴 Resolved", "callback_data": f"/admin_set_{ticket_id}_Resolved"}],
            [{"text": "🔙 Cancel", "callback_data": f"/view_{ticket_id}"}]
        ]

    @staticmethod
    def admin_wp_list_grid(permits: list, status: str = None) -> list:
        grid = []
        for p in permits:
            grid.append([{"text": f"📄 Review {p['name']}", "callback_data": f"/adm_wpview_{p['name']}"}])
        if status:
            grid.append([{"text": "🔙 Back to Status", "callback_data": "/admin_wp"}])
        else:
            grid.append([{"text": "🔙 Admin Menu", "callback_data": "/menu"}])
        return grid

    @staticmethod
    def admin_wp_details_grid(permit_id: str, status: str) -> list:
        grid = []
        if status == "Pending":
            grid.append([{"text": "✅ Approve", "callback_data": f"/adm_wpact_{permit_id}_Approved"}, {"text": "❌ Reject", "callback_data": f"/adm_wpact_{permit_id}_Rejected"}])
        elif status == "Approved":
            grid.append([{"text": "🏁 Mark Completed", "callback_data": f"/adm_wpact_{permit_id}_Completed"}, {"text": "❌ Reject", "callback_data": f"/adm_wpact_{permit_id}_Rejected"}])
        elif status == "Rejected":
            grid.append([{"text": "✅ Approve (Re-open)", "callback_data": f"/adm_wpact_{permit_id}_Approved"}])
        elif status == "Completed":
            grid.append([{"text": "🔄 Re-open Permit", "callback_data": f"/adm_wpact_{permit_id}_Pending"}])
        grid.append([{"text": "🔙 Back to List", "callback_data": "/admin_wp"}])
        return grid

    @staticmethod
    def resident_violations_grid(reports: list) -> list:
        grid = []
        for r in reports:
            rep_id = str(r.get('name') or 'Unknown')
            short_id = rep_id.replace("INCIDENT-", "")
            raw_type = r.get('voilation_type') or r.get('violation_type') or 'Violation'
            v_type = str(raw_type)
            status = str(r.get('status') or 'Open')
            block = str(r.get('target_block') or 'Unknown')
            short_type = v_type[:10] + ".." if len(v_type) > 10 else v_type
            
            btn_text = f"👁️ {short_id} | {block} | {short_type} - {status}"
            grid.append([{"text": btn_text, "callback_data": f"/my_viol_{rep_id}"}])
            
        # 👇 CHANGED TO RESIDENT PORTAL
        grid.append([{"text": "🔙 Back to Resident Portal", "callback_data": "/portal_resident"}])
        return grid

    @staticmethod
    def dynamic_select_grid(options: list, callback_prefix: str) -> list:
        grid = []
        for i in range(0, len(options), 2):
            row = [{"text": options[i], "callback_data": f"{callback_prefix}{options[i]}"}]
            if i + 1 < len(options):
                row.append({"text": options[i+1], "callback_data": f"{callback_prefix}{options[i+1]}"})
            grid.append(row)
        grid.append([{"text": "🔙 Back", "callback_data": "/menu"}])
        return grid

    @staticmethod
    def guard_call_resident_telegram(chat_id: str, username: str = None) -> list:
        # 1. First choice: Use the standard web URL if a username exists
        # This works flawlessly on Telegram Web, Desktop, and Mobile.
        if username and str(username).lower() != "none" and str(username).strip() != "":
            clean_user = str(username).replace("@", "").strip()
            return [[{"text": f"📞 Contact @{clean_user} (Telegram)", "url": f"https://t.me/{clean_user}"}]]
            
        # 2. Fallback: Use the deep link ONLY if the user has no username.
        # This works on Mobile and the Telegram Desktop app.
        else:
            return [[{"text": "📞 Contact Resident (Telegram)", "url": f"tg://user?id={chat_id}"}]]

    @staticmethod
    def dynamic_filter_grid(options: list, callback_prefix: str, back_button: tuple = None) -> list:
        grid = []
        row = []
        
        for opt in options:
            row.append({"text": opt, "callback_data": f"{callback_prefix}{opt}"})
            if len(row) == 2:
                grid.append(row)
                row = []
                
        if row:
            grid.append(row)
            
        # 👇 Using your existing method!
        if back_button:
            grid.append([{"text": back_button[0], "callback_data": back_button[1]}])
        else:
            grid.extend(KeyboardBuilder.back_to_menu()) # Use extend, not append!
            
        return grid

    @staticmethod
    def visitor_purpose_grid() -> list:
        options = KeyboardBuilder._fetch_options("Visitor Log", "purpose", ["Guest", "Service", "Maid", "Taxi"])
        return KeyboardBuilder.dynamic_filter_grid(options, "/vpurp_", back_button=("🔙 Main Menu", "/menu"))


    @staticmethod
    def verifier_grid():
        """Main menu grid for the Doc Verifier role."""
        return [
            [{"text": "📄 Verify Owners Documents", "callback_data": "/v_queue_owners"}],
            [{"text": "📄 Verify Tenants Documents", "callback_data": "/v_queue_tenants"}],
            [{"text": "🐾 Verify Pets Documents", "callback_data": "/v_queue_pets"}],
            [{"text": "🚪 Logout", "callback_data": "/logout"}]
        ]

    @staticmethod
    def aoa_monitor_category_grid(status_filter: str, category_counts: dict = None) -> list:
        if category_counts is None:
            category_counts = {}
            
        options = KeyboardBuilder._fetch_options("Maintenance Ticket", "category", ["Handing Over", "Defects Rectification", "Other"])
        
        grid = []
        # Toggle Button
        if status_filter == "open":
            grid.append([{"text": "🔄 Switch to CLOSED Tickets 🔴", "callback_data": "/aoa_monitor_menu_closed"}])
        else:
            grid.append([{"text": "🔄 Switch to OPEN Tickets 🟢", "callback_data": "/aoa_monitor_menu_open"}])
            
        # 2-Column Category Grid with dynamic counts
        row = []
        for cat in options:
            count = category_counts.get(cat, 0)
            btn_text = f"📂 {cat} ({count})"
            
            row.append({"text": btn_text, "callback_data": f"/aoa_list_{status_filter}_{cat}"})
            if len(row) == 2:
                grid.append(row)
                row = []
        if row: grid.append(row)
        
        # 👇 CHANGED TO AOA PORTAL INSTEAD OF /menu
        grid.append([{"text": "🔙 Back to AoA Portal", "callback_data": "/portal_aoa"}])
        return grid

    @staticmethod
    def aoa_flat_list_grid(flats: list, status_filter: str) -> list:
        """Renders unique flat numbers as buttons in a 2-column layout."""
        grid = []
        row = []
        for flat in flats:
            row.append({"text": f"🏢 {flat}", "callback_data": f"/aoa_flat_tkt_{status_filter}_{flat}"})
            if len(row) == 2:
                grid.append(row)
                row = []
        if row: grid.append(row)
        
        grid.append([{"text": "🔙 Back to Categories", "callback_data": f"/aoa_monitor_menu_{status_filter}"}])
        return grid

    @staticmethod
    def aoa_category_flat_list_grid(flats: list, status_filter: str, category: str) -> list:
        """Renders flats that have tickets in this specific category."""
        grid = []
        row = []
        for flat in flats:
            row.append({"text": f"🏢 {flat}", "callback_data": f"/aoa_cat_flat_tkt_{status_filter}_{flat}_{category}"})
            if len(row) == 2:
                grid.append(row)
                row = []
        if row: grid.append(row)
        
        # 👇 FIX 1: This now correctly returns to the main Category selection menu
        grid.append([{"text": "🔙 Back to Categories", "callback_data": f"/aoa_monitor_menu_{status_filter}"}])
        return grid

    @staticmethod
    def aoa_ticket_list_grid(tickets: list, status_filter: str, back_callback: str) -> list:
        """Renders the actual tickets in a 2-column grid with a dynamic back button."""
        grid = []
        row = []
        
        for t in tickets:
            creation = t.get('creation', '')
            # Extracting just the YYYY-MM-DD format (first 10 characters)
            formatted_date = creation[:10] if creation and len(creation) >= 10 else creation
            
            # Cleaned up the text to fit beautifully in 2 columns
            btn_text = f"🎫 {t.get('name')} ({formatted_date})"
            
            row.append({"text": btn_text, "callback_data": f"/aoa_view_{t.get('name')}"})
            
            # Push the row to the grid once it has 2 buttons
            if len(row) == 2:
                grid.append(row)
                row = []
                
        # Catch any remaining odd button
        if row: 
            grid.append(row)
        
        # Add the dynamic back button at the very bottom
        grid.append([{"text": "🔙 Back", "callback_data": back_callback}])
        
        return grid
    @staticmethod
    def aoa_ticket_view_grid(ticket_name: str, flat_number: str, status: str, back_callback: str) -> list:
        grid = []
        if status in ["Open", "Pending", "In Progress", "Assigned"]:
            grid.append([{"text": "👀 Claim Ticket", "callback_data": f"/claim_ticket_{ticket_name}"}])
            
        grid.append([{"text": "💬 Message Resident", "callback_data": f"/msg_resident_{flat_number}"}])
        
        # 👇 FIX: Use the dynamic callback to return to the flat's ticket list
        grid.append([{"text": "🔙 Back", "callback_data": back_callback}])
        return grid

    @staticmethod
    def aoa_wp_list_grid(permits: list, current_status: str) -> list:
        grid = []
        
        # Toggle Button at the top
        if current_status == "Pending":
            grid.append([{"text": "🔄 View APPROVED Permits", "callback_data": "/aoa_wp_list_Approved"}])
        else:
            grid.append([{"text": "🔄 View PENDING Permits", "callback_data": "/aoa_wp_list_Pending"}])
            
        # Permit List
        for p in permits:
            btn_text = f"🏠 {p.get('flat_number')} | {p.get('contractor_name')}"
            grid.append([{"text": btn_text, "callback_data": f"/aoa_wpview_{p.get('name')}"}])
            
        grid.append([{"text": "🔙 Back to AOA Portal", "callback_data": "/portal_aoa"}])
        return grid
        
    @staticmethod
    def aoa_wp_action_grid(permit_id: str, current_status: str) -> list:
        grid = []
        
        # Render actions based on status
        if current_status == "Pending":
            grid.append([
                {"text": "✅ Approve", "callback_data": f"/aoa_wpact_{permit_id}_Approved"},
                {"text": "❌ Reject", "callback_data": f"/aoa_wpact_{permit_id}_Rejected"}
            ])
        elif current_status == "Approved":
            grid.append([
                {"text": "⏪ Revert to Pending", "callback_data": f"/aoa_wpact_{permit_id}_Pending"}
            ])
            
        # Dynamic back button
        grid.append([{"text": "🔙 Back to List", "callback_data": f"/aoa_wp_list_{current_status}"}])
        return grid

    @staticmethod
    def resident_vehicles_grid() -> list:
        return [
            [{"text": "➕ Add New Vehicle", "callback_data": "/add_vehicle"}],
            [{"text": "🔙 Back to Portal", "callback_data": "/portal_resident"}]
        ]

    @staticmethod
    def vehicle_type_grid() -> list:
        # Fetch options dynamically from ERPNext, with a fallback list just in case
        options = KeyboardBuilder._fetch_options("Resident Vehicle", "vehicle_type", ["Car", "Bike", "Bicycle", "Other"])
        
        # Use the existing dynamic grid builder to format the buttons
        return KeyboardBuilder.dynamic_filter_grid(
            options, 
            "/vtype_", 
            back_button=("❌ Cancel", "/my_vehicles")
        )
