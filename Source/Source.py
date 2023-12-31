import socket
import base64
import os
import time
from threading import Thread,Event
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.utils import formatdate
import copy
import tkinter as tk
from tkinter import Menu, ttk
import re
import xml.etree.ElementTree as ET
import tkinter.messagebox
import xml.dom.minidom
import email

class MailClient: # Class Gửi và Nhận mail
    
    def __init__(self): # Đặt dữ liệu 
        # Phần cấu hình
        self.username = ""
        self.password = ""
        self.mail_server = ""
        self.smtp_port = 0
        self.pop3_port = 0
        self.autoload_interval = 0
        self.FilePath = ""
        # Phần thông tin 
        self.read = []
        self.current_email_number = 0
        self.current_folder = "Inbox"
        self.mailbox = {
            "Inbox": [],
            "Project": [],
            "Important": [],
            "Work": [],
            "Spam": []
        }
        self.content = {
            "From": str,
            "To": str,
            "CC" : str,
            "Subject": str,
            "Body": str,
            "Attachment":[]
        }
   
    def LoadConfig(self, FilePath):
        script_directory = os.path.dirname(os.path.abspath(__file__))
        xml_file_path = os.path.join(script_directory, FilePath)

        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        # Phần cấu hình
        user_info = root.find('UserInformation')
        self.username = user_info.find('Username').text
        self.password = user_info.find('Password').text
        self.mail_server = user_info.find('MailServer').text
        self.smtp_port = int(user_info.find('SMTP').text)
        self.pop3_port = int(user_info.find('POP3').text)
        self.autoload_interval = int(user_info.find('Autoload').text)

        # Phần thông tin
        self.read = []
        self.current_email_number = 0
        self.current_folder = "Inbox"
        self.mailbox = {
            "Inbox": [],
            "Project": [],
            "Important": [],
            "Work": [],
            "Spam": []
        }
        
        for email in root.find('Emails').findall('Email'):
            self.content = {
                "From": "",
                "To": "",
                "CC": "",
                "Subject": "",
                "Body": "",
                "Attachment": []
            }

            seen = email.find('Seen').text.lower() == 'true'
            self.content['Seen'] = seen

            for field in ['From', 'To', 'CC', 'Subject', 'Body']:
                if email.find(field) is not None:
                    self.content[field] = email.find(field).text 

            attachments = email.find('Attachments')
            if attachments is not None:
                for attachment in attachments.findall('Attachment'):
                    filename = attachment.find('FileName').text
                    source = attachment.find('Source').text
                    self.content['Attachment'].append((filename, source))

            if seen:
                self.read.append(copy.copy(self.content))
            self.PutIntoFolder(copy.copy(self.content))
            self.current_email_number += 1
        
    def ConnectToServer(self, server, port): # Socket Kết nối với server
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server, port))
        return client_socket

    def SendCommand(self, socket, command): # Socket Gửi/Nhận dữ liệu Đến/Từ server
        socket.send(command.encode("utf-8"))
        resp = socket.recv(1024*1024*1024).decode("utf-8")
        return resp
    
    def SendWith_TO(self, msg):
        msg_bytes = msg.as_bytes()
        SMTPSocket = socket.create_connection((self.mail_server, self.smtp_port))
        self.SendCommand(SMTPSocket, f"EHLO {self.username}\r\n")
        self.SendCommand(SMTPSocket, f"MAIL FROM: <{self.username.strip()}>\r\n")
        if msg['To']:
            recipient_list = msg['To'].split(",")
            for recipient_address in recipient_list:
                self.SendCommand(SMTPSocket, f"RCPT TO: <{recipient_address.strip()}>\r\n")
        self.SendCommand(SMTPSocket, f"DATA\r\n")
        SMTPSocket.sendall( msg_bytes + b'\r\n.\r\n')
        self.SendCommand(SMTPSocket, "QUIT\r\n")
        SMTPSocket.close()

    def SendWith_CC(self, msg):
        msg_bytes = msg.as_bytes()
        SMTPSocket = socket.create_connection((self.mail_server, self.smtp_port))
        self.SendCommand(SMTPSocket, f"EHLO {self.username}\r\n")
        self.SendCommand(SMTPSocket, f"MAIL FROM: <{self.username.strip()}>\r\n")
        if msg['CC']:
            recipient_list = msg['CC'].split(",")
            for recipient_address in recipient_list:
                self.SendCommand(SMTPSocket, f"RCPT TO: <{recipient_address.strip()}>\r\n")
        self.SendCommand(SMTPSocket, f"DATA\r\n")
        SMTPSocket.sendall( msg_bytes + b'\r\n.\r\n')
        self.SendCommand(SMTPSocket, "QUIT\r\n")
        SMTPSocket.close()

    def SendWith_BCC(self, msg):
        msg_bytes = msg.as_bytes()
        SMTPSocket = socket.create_connection((self.mail_server, self.smtp_port))
        self.SendCommand(SMTPSocket, f"EHLO {self.username}\r\n")
        self.SendCommand(SMTPSocket, f"MAIL FROM: <{self.username.strip()}>\r\n")
        if msg['To']:
            self.SendCommand(SMTPSocket, f"RCPT TO: <{msg['To'].strip()}>\r\n")
        self.SendCommand(SMTPSocket, f"DATA\r\n")
        SMTPSocket.sendall( msg_bytes + b'\r\n.\r\n')
        self.SendCommand(SMTPSocket, "QUIT\r\n")
        SMTPSocket.close()
    
    def SendMail(self,to,cc,bcc,subject,content,attachments): # Gửi Mail đến server bằng giao thức SMTP
        # Gửi tin nhắn bằng To
        if to:
            msg = MIMEMultipart()
            msg['Date'] = formatdate(localtime=True)
            msg['From'] = self.username
            msg['To'] = to
            msg['Subject'] = subject

            # Dính kèm nội dung văn bản
            TextPart = MIMEText(content + '\r\n')
            msg.attach(TextPart)

            # Đính kèm tập tin
            for attachment in attachments:
                if os.path.exists(attachment) and os.path.getsize(attachment) <= (3 * 1024 * 1024):
                    with open(attachment, 'rb') as file:
                        part = MIMEApplication(file.read(), Name=os.path.basename(attachment))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                        msg.attach(part)
            
            # Gửi mail
            self.SendWith_TO(msg)
        # Gửi tin nhắn bằng CC
        if cc:
            msg = MIMEMultipart()
            msg['Date'] = formatdate(localtime=True)
            msg['From'] = self.username
            msg['To'] = to
            msg['CC'] = cc
            msg['Subject'] = subject
            # Dính kèm nội dung văn bản
            TextPart = MIMEText(content + '\r\n')
            msg.attach(TextPart)
            # Đính kèm tập tin
            for attachment in attachments:
                if os.path.exists(attachment) and os.path.getsize(attachment) <= (3 * 1024 * 1024):
                    with open(attachment, 'rb') as file:
                        part = MIMEApplication(file.read(), Name=os.path.basename(attachment))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                        msg.attach(part)
            # Gửi mail
            self.SendWith_CC(msg)
        # Gửi tin nhắn bằng BCC
        if bcc:
            recipient_list = bcc.split(",")
            for recipient_address in recipient_list:
                msg = MIMEMultipart()
                msg['Date'] = formatdate(localtime=True)
                msg['From'] = self.username
                msg['To'] = bcc
                msg['Subject'] = subject

                # Dính kèm nội dung văn bản
                TextPart = MIMEText(content + '\r\n')
                msg.attach(TextPart)

                # Đính kèm tập tin
                for attachment in attachments:
                    if os.path.exists(attachment) and os.path.getsize(attachment) <= (3 * 1024 * 1024):
                        with open(attachment, 'rb') as file:
                            part = MIMEApplication(file.read(), Name=os.path.basename(attachment))
                            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment)}"'
                            msg.attach(part)
                # Gửi mail
                self.SendWith_BCC(msg)
        # In ra khi đã hoàn tất việc gửi email
        print("Email sent successfully")
    
    def PutIntoFolder(self, content):
        def contains_word(text, words):
            return any(word in text for word in words)
        # Inbox
        self.mailbox['Inbox'].append(content)
        # Project
        project_words = ["testing.com", "fit.hcmus.edu.vn"]
        if contains_word(content.get('From', ''), project_words):
            self.mailbox["Project"].append(content)
        # Important
        important_words = ["urgent", "ASAP"]
        if contains_word(content.get('Subject', ''), important_words):
            self.mailbox['Important'].append(content)
        # Work
        work_words = ["report", "meeting"]
        if contains_word(content.get('Body', ''), work_words):
            self.mailbox["Work"].append(content)
        # Spam
        spam_words = ["virus", "hack", "crack"]
        if contains_word(content.get('Subject', ''), spam_words) or contains_word(content.get('Body', ''), spam_words):
            self.mailbox['Spam'].append(content)
  
    def ReadMainContent(self, text):
        email_data = {}
        attachments = []
        header, body = text.split('\r\n\r\n',1)
        header_match_to = re.search(r'Date: (.+?)\r\nFrom: (.+?)\r\nTo: (.+?)\r\nSubject: (.+?)\r\n', text)
        header_match_to_cc = re.search(r'Date: (.+?)\r\nFrom: (.+?)\r\nTo: (.+?)\r\nCC: (.+?)\r\nSubject: (.+?)\r\n', text)
        if header_match_to_cc:
            email_data['Date'] = header_match_to_cc.group(1)
            email_data['From'] = header_match_to_cc.group(2)
            email_data['To'] = header_match_to_cc.group(3)
            email_data['CC'] = header_match_to_cc.group(4)
            email_data['Subject'] = header_match_to_cc.group(5)
        elif header_match_to:
            email_data['Date'] = header_match_to.group(1)
            email_data['From'] = header_match_to.group(2)
            email_data['To'] = header_match_to.group(3)
            email_data['Subject'] = header_match_to.group(4)
        part = body.split('--=========')
        content = part[1].split('\r\n\r\n',1)
        email_data['Body'] = content[1].replace('\r\n','') if len(content) >= 2 else ''
        have_file = True if len(part) > 2 else False
        if have_file :
            attachment = part[2:len(part)-1]
            for at in attachment:
                type_file = at.split('\r\n\r\n')[0].split('\r\n')[1].split('=',1)[1].replace('"','').strip()
                source_file = at.split('\r\n\r\n')[1].strip()
                attachments.append((type_file,source_file))
            email_data['Attachment'] = attachments
        return email_data

    def LoadMail(self): # Tải nội dung email từ server bằng giao thức pop3
        POP3Socket = self.ConnectToServer(self.mail_server, self.pop3_port)
        resp = POP3Socket.recv(1024).decode()
        self.SendCommand(POP3Socket,f"USER {self.username}\r\n")
        self.SendCommand(POP3Socket,f"PASS {self.password}\r\n")
        self.SendCommand(POP3Socket,f"STAT\r\n")
        list_response = self.SendCommand(POP3Socket, "LIST\r\n") 
        email_lines = list_response.split('\r\n')[1:-2]  
        num = len(email_lines)
    
        if num > self.current_email_number:
            for i in range(self.current_email_number + 1,num + 1):
                response = self.SendCommand(POP3Socket,f"RETR {i}\r\n")
                
                msg = email.message_from_string(response)

                msg = self.ReadMainContent(response)

                # Put mail into folder
                self.PutIntoFolder(msg)

            self.current_email_number = num

        self.SendCommand(POP3Socket, f"QUIT\r\n")
        POP3Socket.close()

    def ViewMails(self):
        # Cập nhật nội dung email trong folder hiện tại
        folder = self.current_folder
        # In email ra
        print(f"This is the email list in <{folder}> folder:")
        for i, email in enumerate(self.mailbox[folder], start=1):
            read_status = "(Seen) " if email.get('id', '') in self.read else "(Unread) "
            print(f"{i}. {read_status}<{email.get('From', 'Unknown')}>, <{email.get('Subject', 'No Subject')}>")
            
    def SaveFile(self,Source,FileName): # Lưu File từ email xuống
        attachment_source = Source
        attachment_data = base64.b64decode(attachment_source)
        with open(FileName, "wb") as f:
            f.write(attachment_data)

    def ReadMail(self): # Đọc Nội dung email
        email_index = int(input(" What email do you want to read (Press enter to exit): "))
        if 0 < email_index <= len(self.mailbox[self.current_folder]):
            if self.mailbox[self.current_folder][email_index - 1] not in self.read:
                self.read.append(copy.copy(self.mailbox[self.current_folder][email_index - 1]))
            print(f"Email content of {email_index}-th email:")

            for key, value in self.mailbox[self.current_folder][email_index-1].items():
                if key == 'Attachment':
                    if len(value)!=0:
                        for i,file in enumerate(value,start=1) :
                            print(f"Attachment #{i} : {file[0]}")
                        question = int(input("Is there a file in this email you want to download? (1: Yes / 2: No): "))
                        if question == 1:
                            choose = [int(choose) for choose in input('Select the file you want to download (1,2,3,...,n): ').split(',')]
                            for x in choose:
                                filename = value[x - 1][0]
                                source = value[x - 1][1]
                                self.SaveFile(source,filename)
                        elif question == 2:
                            print("Done!\n")
                else:
                    if key == 'Body': print(f"{value}")
                    else:
                        print(f"{key}: {value}")               

    def SaveData(self, FilePath):
        root = ET.Element("Data")

        user_info = ET.SubElement(root, "UserInformation")
        ET.SubElement(user_info, "Username").text = str(self.username)
        ET.SubElement(user_info, "Password").text = str(self.password)
        ET.SubElement(user_info, "MailServer").text = str(self.mail_server)
        ET.SubElement(user_info, "SMTP").text = str(self.smtp_port)
        ET.SubElement(user_info, "POP3").text = str(self.pop3_port)
        ET.SubElement(user_info, "Autoload").text = str(self.autoload_interval)

        emails = ET.SubElement(root, "Emails")

        for mail in self.mailbox["Inbox"]:
            email_element = ET.SubElement(emails, "Email")
            ET.SubElement(email_element, "Seen").text = "True" if mail in self.read else "False"

            for key, value in mail.items():
                if key == 'Attachment':
                    attachments = ET.SubElement(email_element, "Attachments")
                    for filename, source in value:
                        attachment = ET.SubElement(attachments, "Attachment")
                        ET.SubElement(attachment, "FileName").text = str(filename)
                        ET.SubElement(attachment, "Source").text = str(source)
                else:
                    ET.SubElement(email_element, key).text = str(value)

        # Tạo một biểu diễn chuỗi bằng XML được định dạng
        xml_str = xml.dom.minidom.parseString(ET.tostring(root)).toprettyxml(indent="    ")

        with open(FilePath, "w") as xml_file:
            xml_file.write(xml_str)

    def AutoloadMails(self):
        while True:
            self.LoadMail()
            time.sleep(self.autoload_interval)
    
class ConsoleRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)  # Tự động cuộn xuống phía dưới

# Lớp xử lí phần giao diện
class MailClientGUI(tk.Tk):
    def __init__(s, *args, **kwargs):
        tk.Tk.__init__(s, *args, **kwargs)

        # Thiết lập thông số cửa sổ
        s.title("Mail Client")
        s.geometry("590x400")
        # Khởi tạo MailClient
        s.mail_client = MailClient()
        s.stop_event = Event()
        
        # Tạo menu chính
        s.menu_button = ttk.Button(s, text="Email Menu", command=s.Show_menu,width =100,style="TButton")
        s.menu_button.pack(pady=100, padx=250, anchor=tk.NW)
        s.style = ttk.Style()
        s.style.configure("TButton", font=("Helvetica", 11))

        s.resizable(False, False)

        s.menu = Menu(s, tearoff=0)
        s.menu.add_command(label="Sign In", command=s.Create_config_file)
        s.menu.add_separator()
        s.menu.add_command(label="Exit", command=s.Exit_program)

    def Show_main_menu(self):
        # Tạo menu chính sau khi login
        main_menu = Menu(self, tearoff=0)
        self.menu_button.pack_forget()  # Xóa nút menu
        main_menu.add_command(label="Send Email", command=self.Send_email)
        main_menu.add_command(label="MailBox", command=self.Mail_box)
        main_menu.add_separator()
        main_menu.add_command(label="Logout", command=self.Logout)
        main_menu.add_command(label="Exit", command=self.Exit_program)

        # Gắn menu chính vào cửa sổ chính
        self.config(menu=main_menu)
        
    def Show_menu(s):
        # Hiển thị menu ở vị trí của button
        s.menu.post(s.menu_button.winfo_rootx(), s.menu_button.winfo_rooty() + s.menu_button.winfo_height())

    def Create_config_file(self):
        # Tạo cửa sổ pop-up để nhập thông tin cấu hình
        config_dialog = tk.Toplevel(self)
        config_dialog.title("LOGIN")
        width = 250
        height = 100
        # Lấy kích thước màn hình
        screen_width = config_dialog.winfo_screenwidth()
        screen_height = config_dialog.winfo_screenheight()

        # Tính toán vị trí để đưa cửa sổ pop-up ra giữa màn hình
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        # Đặt kích thước và vị trí của cửa sổ pop-up
        config_dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        # Tạo các ô nhập liệu
        username_label = tk.Label(config_dialog, text="Username:")
        username_entry = tk.Entry(config_dialog, width=30)
        username_label.grid(row=1, column=0, sticky=tk.E)
        username_entry.grid(row=1, column=1)

        password_label = tk.Label(config_dialog, text="Password:")
        password_entry = tk.Entry(config_dialog, width=30, show="*")
        password_label.grid(row=2, column=0, sticky=tk.E)
        password_entry.grid(row=2, column=1)
        config_dialog.resizable(False, False)
        def save_config():
            # Lấy thông tin từ các ô nhập liệu
            username = username_entry.get()
            password = password_entry.get()
            mail_server = '127.0.0.1'
            smtp_port = "2225"
            pop3_port = "3335"
            autoload_interval = "10"

            # Kiểm tra xem các trường thông tin có được nhập hay không
            if not all([username, password, mail_server, smtp_port, pop3_port, autoload_interval]):
                tkinter.messagebox.showwarning("Missing Information", "Please fill in all fields.")
                return

            # Lưu thông tin vào đối tượng MailClient
            mail_client.username = username
            mail_client.password = password
            mail_client.mail_server = mail_server
            mail_client.smtp_port = int(smtp_port)
            mail_client.pop3_port = int(pop3_port)
            mail_client.autoload_interval = int(autoload_interval)
            mail_client.FilePath = "Client_" + mail_client.username + ".xml"

            # Lưu cấu hình
            file_path = mail_client.FilePath
            if os.path.exists(file_path):
                mail_client.LoadConfig(file_path)
            else:
                mail_client.SaveData(file_path)
            # Bắt đầu luồng
            self.autoload_thread = Thread(target=self.mail_client.AutoloadMails, args=(self.stop_event,))
            self.autoload_thread.start()
            # Đóng cửa sổ pop-up
            config_dialog.destroy()
            tkinter.messagebox.showinfo("Login Successful", f"Welcome <{username}>!")
            self.Show_main_menu()
        # Tạo nút để lưu cấu hình
        save_button = tk.Button(config_dialog, text="Log in", command=save_config)
        save_button.grid(row=7, columnspan=2)

    def Logout(self):
        self.menu.destroy()  
        self.menu_button.destroy()  
        self.title("Mail Client") 
        self.geometry("590x400") 
        self.destroy()
        if self.autoload_thread:
            # Đặt biến cờ để yêu cầu luồng dừng
            self.stop_event.set()
            # Đợi cho luồng dừng
            self.autoload_thread.join()
        self.__init__() 

    def Send_email(s):
        # Tạo cửa sổ pop-up để nhập thông tin email
        email_dialog = tk.Toplevel(s)
        email_dialog.title("Send Email")
        email_dialog.geometry("590x400")
        # Tạo các ô nhập liệu
        to_label = tk.Label(email_dialog, text="To:")
        to_entry = tk.Text(email_dialog, width=60, height = 1)
        to_label.grid(row=1, column=0, sticky=tk.E)
        to_entry.grid(row=1, column=1)

        cc_label = tk.Label(email_dialog, text="CC:")
        cc_entry = tk.Text(email_dialog, width = 60, height = 1)
        cc_label.grid(row=2, column=0, sticky=tk.E)
        cc_entry.grid(row=2, column=1)

        bcc_label = tk.Label(email_dialog, text="BCC:")
        bcc_entry = tk.Text(email_dialog, width = 60, height = 1)
        bcc_label.grid(row=3, column=0, sticky=tk.E)
        bcc_entry.grid(row=3, column=1)

        subject_label = tk.Label(email_dialog, text="Subject:")
        subject_entry = tk.Text(email_dialog, width = 60, height = 1)
        subject_label.grid(row=4, column=0, sticky=tk.E)
        subject_entry.grid(row=4, column=1)

        content_label = tk.Label(email_dialog, text="Content:")
        content_text = tk.Text(email_dialog, width=60, height=5)  # Sử dụng Text thay vì Entry
        content_label.grid(row=5, column=0, sticky=tk.E)
        content_text.grid(row=5, column=1)

        attachments_label = tk.Label(email_dialog, text="Num_Attach_file:")
        num_attachments_entry = tk.Entry(email_dialog,width = 80)
        attachments_label.grid(row=6, column=0, sticky=tk.E)
        num_attachments_entry.grid(row=6, column=1)

        attachments = []
        def Add_attachments():
            nonlocal attachments  # Sử dụng nonlocal để truy cập biến ở mức độ của hàm send_email
            num_attachments = int(num_attachments_entry.get())
            for i in range(num_attachments):
                label = tk.Label(email_dialog, text=f"Attachment {i + 1}:")
                entry = tk.Entry(email_dialog, width=80)
                label.grid(row=8 + i, column=0, sticky=tk.E)
                entry.grid(row=8 + i, column=1)
                attachments.append(entry)

        add_attachments_button = tk.Button(email_dialog, text="Add Attachments", command=Add_attachments)
        add_attachments_button.grid(row=7, columnspan=2)

        def Send_email_from_dialog():
            nonlocal attachments
            print("Checking email_dialog:", email_dialog)
            print("Attachments:", attachments)

            if email_dialog and email_dialog.winfo_exists():
                attachment_paths = [entry.get() for entry in attachments]
                print("Attachment Paths:", attachment_paths)

                # Gửi thông tin đến hàm send_email của MailClient
                mail_client.SendMail(
                    to_entry.get("1.0", "end-1c"),
                    cc_entry.get("1.0", "end-1c"),
                    bcc_entry.get("1.0", "end-1c"),
                    subject_entry.get("1.0", "end-1c"),
                    content_text.get("1.0", "end-1c"),
                    attachment_paths
                )
                tkinter.messagebox.showinfo("Email Sent", "Email sent successfully!")

        # Đóng cửa sổ pop-up
                email_dialog.destroy()
            else:
                print("Error: email_dialog is not available.")

        send_button = tk.Button(email_dialog, text="Send Email", command=Send_email_from_dialog)
        send_button.grid(row=0, columnspan=2)
        
    def Exit_program(s):
        # Lưu cấu hình trước khi thoát
        mail_client.SaveData(mail_client.FilePath)
        s.destroy()

    def Mail_box(self):
        # Gọi hàm load_emails từ MailClient để cập nhật nội dung email
        mail_client.LoadMail()

        # Tạo cửa sổ Mailbox
        mailbox_window = tk.Toplevel(self)
        mailbox_window.title("Mailbox")
        mailbox_window.geometry("590x400")

        # Hiển thị danh sách các folder
        folder_listbox = tk.Listbox(mailbox_window, selectmode=tk.SINGLE)
        folder_listbox.pack(side=tk.LEFT, fill=tk.Y)

        for folder in mail_client.mailbox.keys():
            folder_listbox.insert(tk.END, folder)

        # Tạo Text widget để hiển thị nội dung email
        email_text = tk.Text(mailbox_window, wrap=tk.WORD, width=50, height=20)
        email_text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Tạo Entry widget để nhập số thứ tự email
        email_number_entry = tk.Entry(mailbox_window, width=10)
        email_number_entry.pack()

        # Hàm hiển thị email khi chọn folder
        def Show_emails():
            # Xóa nội dung hiện tại trong Text widget
            email_text.delete(1.0, tk.END)

            # Hiển thị danh sách email trong Text widget
            for i, email in enumerate(mail_client.mailbox[mail_client.current_folder], start=1):
                read_status = "(Seen) " if email in mail_client.read else "(Unread) "
                email_text.insert(tk.END, f"{i}. {read_status}<{email['From']}>, <{email['Subject']}>\n")

        def View_email():
            try:
                email_number = int(email_number_entry.get()) - 1
                selected_email = mail_client.mailbox[mail_client.current_folder][email_number]
                if selected_email not in mail_client.read:
                    mail_client.read.append(copy.copy(selected_email))
                # Xóa nội dung hiện tại trong Text widget
                email_text.delete(1.0, tk.END)

                # Hiển thị nội dung email trong Text widget
                email_text.insert(tk.END, f"Email content of {email_number + 1}-th email:\n")
                for key, value in selected_email.items():
                    if key == 'Attachment':
                        if value:
                            for i, file_info in enumerate(value, start=1):
                                email_text.insert(tk.END, f"Attachment #{i}: {file_info[0]}\n")
                            question = tkinter.simpledialog.askstring("Download Attachment",
                                                                    "Which attachment do you want to download? "
                                                                    )
                            if question:
                                choices = [int(choice.strip()) for choice in question.split(',')]
                
                                if all(1 <= choice <= len(value) for choice in choices):
                                    for choice in choices:
                                        chosen_file = value[choice - 1]
                                        filename, source = chosen_file[0], chosen_file[1]
                                        mail_client.SaveFile(source, filename)
                                        email_text.insert(tk.END, f"Attachment downloaded: {filename}\n")
                            else:
                                email_text.insert(tk.END, "No attachment downloaded.\n")
                    else:
                        if key == 'Body':
                            email_text.insert(tk.END, f"{value}\n")
                        else:
                            email_text.insert(tk.END, f"{key}: {value}\n")
            except (ValueError, IndexError):
                tkinter.messagebox.showwarning("Invalid Input", "Please enter a valid email number.")

        # Xác định hàm xử lý sự kiện khi chọn một folder
        def Select_folder(event):
            selected_index = folder_listbox.curselection()
            if selected_index:
                mail_client.current_folder = folder_listbox.get(selected_index)
                Show_emails()

        # Gán hàm xử lý sự kiện cho danh sách folder
        folder_listbox.bind("<<ListboxSelect>>", Select_folder)

        # Tạo Button để kích hoạt hàm ViewMails
        view_emails_button = tk.Button(mailbox_window, text="View", command=View_email)
        view_emails_button.pack()

if __name__ == "__main__":
    mail_client = MailClient()
    app = MailClientGUI()
    app.mainloop()
    