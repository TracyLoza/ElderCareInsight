from django.http import HttpResponse
from django.shortcuts import render

def index(request): #main
    return HttpResponse("<h1>hOME</h1>")

def home(response):
    return render(response, "main/home.html",{})

def patient(response):
    #    content = {"hr":90}
    # return render(response, "main/patient.html", content)
    return render(response, "main/patient.html", {})

def patient_list(response):
    return render(response, "main/patient_list.html", {})

def settings(response):
    return render(response, "main/settings.html", {})

def about(response):
    return render(response, "main/about.html", {})

def boot(response):
    return render(response, "main/boot.html", {})
