#!/bin/python

import tkinter as tk
from tkinter import ttk,scrolledtext
import os
import fcntl
import json
import atexit
from subprocess import Popen,PIPE,STDOUT,DEVNULL
from threading import Thread,Event
import shutil
import time
from typing import Callable,Any

#singleton
class Provider:        
    def __init__(self) -> None:
       
        try:
            f=open("config.json","r")
            self.config=json.load(f)
            f.close()
            if not Provider.check_keys(self.config,["version","data","profile","last_profile","last_version","debug_mcpe"]):
                raise ValueError
            print("load config.json")
        except:
            self.config=dict()
            self.config["version"]="~/.local/share/mcpelauncher/versions"
            self.config["data"]="~/.local/share/mcpelauncher"
            self.config["profile"]="accounts"
            self.config["debug_mcpe"]=False

        self.update_profile()
        self.update_version()
        self.instances=[]
        atexit.register(self.export_config)

    def switcher_is_not_setup(self)->bool:
        if os.path.isdir("xal") and not os.path.islink("xal"):
            pass

    def update_profile(self):
        self.profile_list=Provider.list_directory(self.config["profile"])
        if len(self.profile_list):
            if not ("last_profile" in self.config and self.config["last_profile"] in self.profile_list):
                self.config["last_profile"]=self.profile_list[-1]

    def update_version(self):
        self.version_list=Provider.list_directory(self.config["version"])
        if len(self.version_list):
            if not ("last_version" in self.config and self.config["last_version"] in self.version_list):
                self.config["last_version"]=self.version_list[-1]

    def get_versions(self)->list[str]:
        return self.version_list

    def get_last_version(self)->str:
        return self.config["last_version"]

    def select_version(self,version:str):
        if version in self.version_list:
            self.config["last_version"]=version

    def has_version_available(self)->bool:
        return len(self.version_list)!=0

    def get_profiles(self)->list[str]:
        return self.profile_list

    def get_last_profile(self)->str:
        return self.config["last_profile"]

    def has_profile_available(self)->bool:
        return len(self.profile_list)!=0

    def select_profile(self,profile:str):
        if profile in self.profile_list:
            self.config["last_profile"]=profile

    def run_game_instance(self)->bool:
        program=os.getcwd()
        status=True

        try:
            version=os.path.abspath(os.path.expanduser(self.config["version"]))
            data=os.path.abspath(os.path.expanduser(self.config["data"]))
            profile=os.path.abspath(os.path.expanduser(self.config["profile"]))

            os.chdir(data+"/games/com.mojang")
            for item in os.listdir("."):
                if item.endswith(".dat"):
                    os.remove(item)
            if os.path.isdir("xal") and not os.path.islink("xal"):
                shutil.rmtree("xal") #initial run (delete last account session -> sorry :-) )
            else:
                os.remove("xal")
            os.symlink(profile+"/"+self.config["last_profile"],"xal")
            args=["mcpelauncher-client","-dg",version+"/"+self.config["last_version"],"-dd",data,"-df"] #added -df for 1.19.50 support
            
            if self.config["debug_mcpe"]:
                proc=DebugWindow(args).getProc()
            else:
                proc=Popen(args,stdout=DEVNULL,stderr=DEVNULL)
            
            self.instances.append(proc)

        except:
            status=False
        finally:
            os.chdir(program)
            return status

    def _check_profile_folder(self)->bool:
        profile=os.path.expanduser(self.config["profile"])
        if not os.path.exists(profile):
            try:
                os.makedirs(profile)
            except:
                return False
        return True

    def _profile_operation(self,operation:Callable)->bool:
        status=True
        program=os.getcwd()

        try:
            profile=os.path.expanduser(self.config["profile"])
            os.chdir(profile)
            operation()
        except:
            status=False
        finally:
            os.chdir(program)
            self.update_profile()
            return status


    def add_new_profile(self,profile_name:str)->bool:
        return self._check_profile_folder() and self._profile_operation(lambda:os.mkdir(profile_name))

    def rename_profile(self,profile_name:str,new_profile_name:str)->bool:
        return self._profile_operation(lambda:os.rename(profile_name,new_profile_name))

    def delete_profile(self,profile_name:str)->bool:
        return self._profile_operation(lambda:shutil.rmtree(profile_name))

    def export_config(self):
        try:
            f=open("config.json","w")
            json.dump(self.config,f,indent=4)
            f.close()
        except:
            print("export error")

    @staticmethod
    def check_keys(d:dict,keys:list)->bool:
        for k in keys:
            if not k in d:
                return False
        return True   

    @staticmethod
    def list_directory(path:str)->list[str]:
        program_path=os.getcwd()
        try:
            path=os.path.abspath(os.path.expanduser(path))
            os.chdir(path)
            mylist=list(filter(os.path.isdir,os.listdir()))
            
        except:
            mylist=[]
        finally:
            os.chdir(program_path)
            return mylist
        
class DebugWindow(tk.Toplevel):

    def __init__(self,args:list[str]) -> None:
        super().__init__(Fast_MCPELAUNCHER.window)
        self._proc=Popen(args,stdout=PIPE,stderr=STDOUT)

        self.geometry("616x450")
        self.resizable(False,False)
        self.title("Debug Window")
        self.text=scrolledtext.ScrolledText(self, wrap='word', height = 16,state=tk.DISABLED)
        self.text.place(x=1,y=1,width=616,height=450)
        self.protocol("WM_DELETE_WINDOW", lambda:self._onclosing(0))
        self.bind("<Destroy>",lambda e:self._onclosing(2))
        self.update()

        # set for non-blocking io
        orig_fl = fcntl.fcntl(self._proc.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self._proc.stdout, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)

        self.event=Event()
        self.event.clear()
        self.thread=Thread(target=self._refresh)
        self.thread.start()

    def getProc(self):
        return self._proc

    def _refresh(self):
        while True:
            if self.event.is_set():
                return
            b=self._proc.stdout.read()
            if b:
                self.text.configure(state='normal')
                self.text.insert('end', b)
                self.text.configure(state='disabled')
                self.text.see('end')
            time.sleep(0.1)
        

    def _onclosing(self,value):
        if value==2:
            self.event.set()
            self.thread.join()
            self.destroy()
        elif value==3:
            self._proc.kill()
            self._onclosing(2)
            return
        elif value==0:
            if self._proc.poll() is None:
                MessagePopup(self,"Exit","Do you want to kill the associated proccess?",
                            MessagePopup.YesNoCancel,self._onclosing)
            else:
                self._onclosing(2)
        

class Popup(tk.Frame):
    _background="#2b2929"
    _title_background="#524e4e"
    YesNo=["NO","YES"]
    YesNoCancel=["CANCEL","NO","YES"]
    Ok=["OK"]
    OkCancel=["CANCEL","OK"]

    def __init__(self,master,title:str="FastMCPELauncher Popup"):
        super().__init__(master)
        self.config(width=500,height=380,background=Popup._background,highlightcolor="white",highlightthickness=3)
        self.place(x=56,y=10)

        title_label=tk.Label(self,text=title,background=Popup._title_background,foreground="white",font=("Arial bold",25),relief=tk.FLAT)
        title_label.place(x=0,y=0,relwidth=1)

        self.last_state=[]
        self._elements_disable(master)

        self._listener=None
        self._button_counter=0
        self._get_value_func:Callable=None
        

    def _elements_disable(self,element:tk.Widget):
        if id(element)==id(self):
            return
        if "state" in element.config():
            self.last_state.append((element,element.config()["state"][4]))
            element.config(state=tk.DISABLED)
        for e in element.winfo_children():
            self._elements_disable(e)

    def _elements_restore(self):
        for elt in self.last_state:
            elt[0].config(state=elt[1])

    def _onclosing(self,return_value=None):
        if self._get_value_func and return_value==self._button_counter:
            return_value=self._get_value_func()
        
        self._elements_restore()
        self.destroy()
        
        if self._listener:
            self._listener(return_value)
        

    def text_input(self,defaut_value=None,y=220):
        entry=tk.Entry(self,background=Popup._background,foreground="white",font=("Arial",21),justify="center",insertbackground="white")
        if defaut_value:
            entry.insert(0,defaut_value)
        entry.place(relwidth=1,x=0,height=50,y=y)
        self._get_value_func=entry.get
        entry.focus_set()
        
        return self

    def listbox(self,choices:list[str],y=200,height=100):
        listbox_widget=tk.Listbox(self,background=Popup._background,foreground="white",
                        font=("Arial",15))
        for elt in choices:
            listbox_widget.insert(tk.END,elt)
        listbox_widget.place(x=1,width=470,y=y,height=height)
        scrollbar = tk.Scrollbar(self)
        scrollbar.place(width=30,x=471,y=y,height=height)
        listbox_widget.config(yscrollcommand = scrollbar.set)
        scrollbar.config(command = listbox_widget.yview)
        self._get_value_func=listbox_widget.curselection
        listbox_widget.focus_set()

        return self
        

    def buttons(self,choices:list[str],y=335):
        step=1/len(choices)
        for i in range(len(choices)):
            self._button_counter+=1
            command=eval("lambda:self._onclosing({})".format(self._button_counter),locals())
            button=tk.Button(self,text=choices[i],background=Popup._background,foreground="white",
                    font=("Arial",25),relief=tk.FLAT,command=command)
            button.place(relx=i*step,relwidth=step,height=40,y=y)
        return self

    def set_listener(self,func:Callable[[Any],None]):
        self._listener=func
        return self

    def message(self,text:str,y=150):
        message_label=tk.Message(self,text=text,width=480,background=Popup._background,
                                    foreground="white",font=("Arial",21),borderwidth=0,justify="center")
        message_label.place(y=y,x=0,relwidth=1)
        return self

class MessagePopup(Popup):
    def __init__(self,master,title:str,message:str,choices:list[str]=Popup.Ok,listener:Callable[[Any],None]=None):
        super().__init__(master,title)
        self.message(message).buttons(choices).set_listener(listener)

class InputPopup(Popup):
    def __init__(self,master,title:str,message:str,default_value:str="",listener:Callable[[Any],None]=None):
        super().__init__(master,title)
        self.message(message).buttons(InputPopup.OkCancel).set_listener(listener).text_input(defaut_value=default_value)

class WelcomeTab(ttk.Frame):

    def __init__(self,master):
        super().__init__(master)
        self.img=tk.PhotoImage(file="background.png")
        self.background=tk.Label(self,image=self.img,width=616,height=330)
        self.background.place(x=0,y=0)

        self.bottom=tk.Frame(self,highlightthickness=0)
        self.bottom.place(x=10,y=340,relwidth=1,height=120)

        tk.Label(self.bottom,text="Version",font=("Arial",15)).grid(row=0,column=0)
        tk.Label(self.bottom,text="Profile",font=("Arial",15)).grid(row=0,column=1)

        self.version_selected=tk.StringVar()
        self.profile_selected=tk.StringVar()

        optionmenu_configuration={"state":"readonly","foreground":"white","font":("Arial",20)}

        self.play_button=tk.Button(self.bottom,text="Play",font=("Arial bold",32),fg="white",bg="green",width=7,command=self.run_game)
        self.play_button.grid(row=0,rowspan=2,column=2)

        self.optionmenu1=ttk.Combobox(self.bottom,textvariable=self.version_selected,width=9)
        self.optionmenu1.configure(optionmenu_configuration)
        self.optionmenu1.grid(row=1,column=0)
        self.optionmenu1.bind("<<ComboboxSelected>>",self.update_version)
        
        self.optionmenu2=ttk.Combobox(self.bottom,textvariable=self.profile_selected,width=13)
        self.optionmenu2.configure(optionmenu_configuration)
        self.optionmenu2.grid(row=1,column=1)
        self.optionmenu2.bind("<<ComboboxSelected>>",self.update_profile)
        
        self.optionmenu2.grid(row=1,column=1)
        
        


    def update_elements(self):
        play_button_state=tk.ACTIVE

        if provider.has_version_available():
            self.optionmenu1["values"]=provider.get_versions()
            self.version_selected.set(provider.get_last_version())
        else:
            play_button_state=tk.DISABLED

        if provider.has_profile_available():
            self.optionmenu2["values"]=provider.get_profiles()
            self.profile_selected.set(provider.get_last_profile())
        else:
            play_button_state=tk.DISABLED

        self.play_button.config(state=play_button_state)

    def listener(self,value):
        print(value)

    def run_game(self):
        if not provider.run_game_instance():
            MessagePopup(self,"Error","The game cannot start")

    def update_version(self,event):
        provider.select_version(self.optionmenu1.get())

    def update_profile(self,event):
        provider.select_profile(self.optionmenu2.get())

class InstanceTab(ttk.Frame):
    def __init__(self,master):
        super().__init__(master)

    def update_elements(self):
        pass

class ProfileTab(ttk.Frame):
    def __init__(self,master):
        super().__init__(master)
        self.img=tk.PhotoImage(file="back.png")
        background=tk.Label(self,image=self.img)
        background.place(x=0,y=0)
        add_button=tk.Button(self,text="Add new profile",relief=tk.RAISED,
                        command=lambda:InputPopup(self,"New Profile","Enter the name of the new profile",listener=self.add_new_profile))
        add_button.place(relx=0.5, y=20, anchor=tk.CENTER)

        rename_button=tk.Button(self,text="Rename selected profile",relief=tk.RAISED,command=self._prepare_rename)
        rename_button.place(relx=0.3,relwidth=0.3, y=100, anchor=tk.CENTER)

        rename_button=tk.Button(self,text="Delete selected profile",relief=tk.RAISED,command=self.delete_profile)
        rename_button.place(relx=0.7,relwidth=0.3, y=100, anchor=tk.CENTER)


        frame=tk.Frame(self,width=500,height=220,background="grey",relief=tk.RAISED,borderwidth=10,border=10)
        frame.place(anchor=tk.CENTER,rely=0.6,relx=0.5,width=500,height=220)

        tk.Label(frame,text="list of available profile:",width=50).pack(fill=tk.X)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(fill=tk.BOTH,side=tk.RIGHT)

        self.listbox=tk.Listbox(frame,background="grey",foreground="white",
                            font=("Arial",15))
        self.listbox.pack(fill=tk.BOTH,side=tk.LEFT,expand=tk.TRUE)

        self.listbox.config(yscrollcommand = scrollbar.set)
        scrollbar.config(command = self.listbox.yview)

    def _prepare_rename(self):
        for i in self.listbox.curselection():
            value=self.listbox.get(i)
            InputPopup(self,"Rename Profile","Enter the new name of the profile",default_value=value,
                    listener=lambda v:self.rename_profile(value,v))
        
    
    def delete_profile(self):
        for i in self.listbox.curselection():
            value=self.listbox.get(i)
            if not provider.delete_profile(value):
                MessagePopup(self,"Error","Cannot delete profile{}".format(value))
                return
        self.update_elements()

    def add_new_profile(self,value):
        if type(value)==str and len(value):
            if provider.add_new_profile(value):
                MessagePopup(self,"Success","A profile named {} has been created".format(value),listener=lambda value:self.update_elements())
            else:
                MessagePopup(self,"Error","Cannot create a new profile named {}".format(value))
    
    def rename_profile(self,value,new_value):
        if type(value)==str and len(value):
            if provider.rename_profile(value,new_value):
                MessagePopup(self,"Success","A profile named {} has been renamed to {}".format(value,new_value),listener=lambda value:self.update_elements())
            else:
                MessagePopup(self,"Error","Failed to rename profile to {}".format(new_value))

    
    def update_elements(self):
        self.listbox.delete(0,'end')
        for elt in provider.get_profiles():
            self.listbox.insert(tk.END,elt)
        self.listbox.update()

        

class SettingsTab(ttk.Frame):
    def __init__(self,master):
        super().__init__(master)
        self.img=tk.PhotoImage(file="back.png")
        self.background=tk.Label(self,image=self.img)
        self.background.place(x=0,y=0)

    def update_elements(self):
        pass


class Fast_MCPELAUNCHER(tk.Tk):
    tabs_name=["Welcome","Instances Running","Manage profiles","Settings"]
    tabs_class=[WelcomeTab,InstanceTab,ProfileTab,SettingsTab]
    window:tk.Tk

    def __init__(self) -> None:
        super().__init__()
        Fast_MCPELAUNCHER.window=self
        self.title("Fast MCPELAUNCHER")
        self.geometry("616x450")
        self.resizable(False,False)
        
        style = ttk.Style()
        style.theme_create( "yummy", parent="alt", settings={
                "TNotebook": {
                    "configure": {"tabmargins": [2, 5, 2, 0] ,"background":"#34241c"}
                },
                "TNotebook.Tab": {
                    "configure": {"padding": [5, 1], "background": "grey" ,"font":("Arial",15)},
                    "map": {"background": [("selected", "green")] } 
                },
                "TCombobox": {
                    "configure":{"selectbackground": "grey","fieldbackground": "grey",
                    "background": "green","padding":(0,5,5,5),"arrowsize":30,"postoffset":(0,0,16,0)}
                },
        })
        style.theme_use("yummy")

        self.option_add("*TCombobox*Listbox*foreground", 'white')
        self.option_add("*TCombobox*Listbox*background", 'grey')
        self.option_add("*TCombobox*Listbox*selectBackground", 'green')
        self.option_add("*TCombobox*Listbox*selectForeground", 'white')
        self.option_add("*TCombobox*Listbox*font", ("Arial",20))

        self.tabControl = ttk.Notebook(self) 
        self.tabControl.pack(expand = 1, fill ="both")
        self.tabControl.bind('<<NotebookTabChanged>>',self.tab_callback)

        self.tab_list=[]
        for e,c in zip(Fast_MCPELAUNCHER.tabs_name,Fast_MCPELAUNCHER.tabs_class):
            f=c(self.tabControl)
            self.tab_list.append(f)
            self.tabControl.add(f,text=e)

         
        self.mainloop()

    def tab_callback(self,event):
        current_tab=self.tabControl.index(self.tabControl.select())
        self.tab_list[current_tab].update_elements()

provider=Provider()
Fast_MCPELAUNCHER()
