from django import forms as forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import QueryDict, HttpResponse
from django.shortcuts import redirect, render

from .helpers import add_errors_to_password
from apps.accounts.models import Org, OrgContactInfo, OrgInfo, OrgLocation

from .forms import (
    LoginRegisterForm,
    OrgContactInfoForm,
    OrgForm,
    OrgInfoForm,
    OrgLocationForm,
)

# constants
LOGIN_FORM = "login.html"
REGISTER_FORM = "register.html"
EDIT_ORG_INFO_MODAL = "edit_info_modal.html"
EDIT_ACCOUNT_INFO_MODAL = "edit_account_info_modal.html"
SEARCH_NON_PROFITS_TEMPLATE = "search_non_profits.html"
SEARCH_NON_PROFITS_RESULTS = "search_non_profits_results.html"


@login_required  # type: ignore
def edit_org_info(request):
    if request.method == "PUT":
        request_put = QueryDict(request.body)
        org = request.user.id
        existing_contact_form = OrgContactInfo.objects.get(org=org)
        existing_info_form = OrgInfo.objects.get(org=org)
        existing_location_form = OrgLocation.objects.get(org=org)

        contact_form = OrgContactInfoForm(request_put, instance=existing_contact_form)
        info_form = OrgInfoForm(request_put, instance=existing_info_form)
        location_form = OrgLocationForm(request_put, instance=existing_location_form)

        edit_org_forms = [contact_form, info_form, location_form]
        status = 400

        if all([form.is_valid() for form in edit_org_forms]):
            for form in edit_org_forms:
                new_instance = form.save(commit=False)
                new_instance.org = request.user
                new_instance.save()

            # status defaults to 400, but if everything is valid, then set it to 201
            status = 201

        return render(
            request,
            EDIT_ORG_INFO_MODAL,
            context={"edit_org_forms": edit_org_forms},
            status=status,
        )

    return HttpResponse(status=405)


@login_required  # type: ignore
def edit_account_info(request):
    if request.method == "PUT":
        request_put = QueryDict(request.body)
        org_form = OrgForm(request_put, instance=request.user)
        status = 400

        if org_form.is_valid():
            cleaned_org_form = org_form.cleaned_data
            cur_user = org_form.save(commit=False)

            is_pass_invalid = add_errors_to_password(
                cleaned_org_form["password"], cleaned_org_form["confirm_password"]
            )

            if is_pass_invalid:
                org_form.add_error("password", is_pass_invalid)

            else:
                # status defaults to 400, but if everything is valid, then set it to 201
                cur_user.set_password(cleaned_org_form["password"])
                cur_user.save()
                status = 201

        response = render(
            request,
            EDIT_ACCOUNT_INFO_MODAL,
            context={"edit_info_form": org_form},
            status=status,
        )

        if status == 201:
            response["HX-Redirect"] = "/accounts/login/"

        return response

    return HttpResponse(status=405)


def login_user(request):
    if request.method == "POST":
        login_register_form = LoginRegisterForm(request.POST)

        # essentially just checking if the form isn't empty
        if login_register_form.is_valid():
            login_register = login_register_form.cleaned_data

            # inputted data
            username = login_register["username"]
            password = login_register["password"]
            user = authenticate(request, username=username, password=password)

            # if authenticate returns a user object, the user is valid
            if user:
                login(request, user)

                return redirect("dashboard")

            # else error with the form
            else:
                login_register_form.add_error(None, "Username or password is incorrect")
                return render(request, LOGIN_FORM, {"form": login_register_form})

    # else is a GET request
    else:
        login_register_form = LoginRegisterForm()

        return render(request, LOGIN_FORM, {"form": login_register_form})


def logout_user(request):
    # super simple view :)
    logout(request)

    return redirect("/")


def register_user(request):
    user_info_form = OrgForm(request.POST or None)

    # init the forms
    input_forms = [
        OrgLocationForm(request.POST or None),
        OrgContactInfoForm(request.POST or None),
        OrgInfoForm(request.POST or None),
    ]

    # if the user submitted the form and the form is valid
    if request.method == "POST" and user_info_form.is_valid():
        validated_forms_count = [form.is_valid() for form in input_forms]
        cleaned_user_info_form = user_info_form.cleaned_data

        is_pass_invalid = add_errors_to_password(
            cleaned_user_info_form["password"],
            cleaned_user_info_form["confirm_password"],
        )

        if is_pass_invalid:
            user_info_form.add_error("password", is_pass_invalid)

        if all(validated_forms_count) and not is_pass_invalid:
            # inital save on the new user
            new_user = user_info_form.save(commit=False)
            new_user.set_password(cleaned_user_info_form["password"])
            new_user.save()

            # save forms
            for form in input_forms:
                newform = form.save(commit=False)
                newform.org = new_user
                newform.save()

            return redirect("/accounts/login/")

    return render(
        request,
        REGISTER_FORM,
        {"forms": [user_info_form] + input_forms},
    )


def search_non_profits(request):
    orgs = Org.objects.all().select_related("orglocation")
    return render(request, SEARCH_NON_PROFITS_TEMPLATE, context={"orgs": orgs})


def search_non_profits_results(request):
    is_org = request.GET.get("org")
    search = request.GET.get("search")

    if is_org == "org":
        orgs = Org.objects.filter(username__trigram_similar=search).select_related(
            "orglocation"
        )

    else:
        orgs = (
            Org.objects.all()
            .select_related("orglocation")
            .filter(orglocation__region__trigram_similar=search)
        )

    return render(
        request,
        SEARCH_NON_PROFITS_RESULTS,
        context={"orgs": orgs, "search": search, "org": is_org},
    )
