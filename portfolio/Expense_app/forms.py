from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q
from django.utils import timezone

from .models import Category, Expense, PlannedExpense, Profile

User = get_user_model()


class StyledFormMixin:
    """Apply daisyUI classes to every widget so templates stay clean."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "toggle toggle-primary"
            elif isinstance(widget, forms.Select):
                css = "select w-full"
            elif isinstance(widget, forms.Textarea):
                css = "textarea w-full"
                widget.attrs.setdefault("rows", 3)
            else:
                css = "input w-full"
            widget.attrs["class"] = f"{css} {widget.attrs.get('class', '')}".strip()


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


def money_widget():
    return forms.NumberInput(attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal", "placeholder": "0.00"})


class UserCategoryMixin:
    """Restrict the category dropdown to the current user's categories."""

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if "category" in self.fields:
            self.fields["category"].queryset = Category.objects.filter(user=user)
            self.fields["category"].empty_label = "Select a category"


class SignUpForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=True, help_text="Used for budget alerts and password resets.")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class ExpenseForm(StyledFormMixin, UserCategoryMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["amount", "category", "date", "description", "payment_method", "notes"]
        widgets = {
            "amount": money_widget(),
            "date": DateInput(),
            "description": forms.TextInput(attrs={"placeholder": "e.g. Lunch with team"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional"}),
        }

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate() + timedelta(days=366):
            raise forms.ValidationError("That date is too far in the future. Use Plans for upcoming expenses.")
        return value


class QuickExpenseForm(ExpenseForm):
    class Meta(ExpenseForm.Meta):
        fields = ["amount", "category", "description", "date"]


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "color", "monthly_budget"]
        widgets = {"monthly_budget": money_widget()}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        clash = Category.objects.filter(user=self.user, name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("You already have a category with this name.")
        return name


class CategoryDeleteForm(forms.Form):
    move_to = forms.ModelChoiceField(
        queryset=Category.objects.none(), required=False, empty_label="Choose a category",
        label="Move its expenses and plans to",
        widget=forms.Select(attrs={"class": "select w-full"}),
    )

    def __init__(self, *args, category, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category
        self.needs_target = category.expenses.exists() or category.planned_expenses.exists()
        self.fields["move_to"].queryset = Category.objects.filter(user=category.user).exclude(pk=category.pk)
        self.fields["move_to"].required = self.needs_target


class PlannedExpenseForm(StyledFormMixin, UserCategoryMixin, forms.ModelForm):
    class Meta:
        model = PlannedExpense
        fields = ["title", "amount", "category", "due_date", "recurrence", "notes"]
        widgets = {
            "amount": money_widget(),
            "due_date": DateInput(),
            "title": forms.TextInput(attrs={"placeholder": "e.g. Rent, Netflix, School fees"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional"}),
        }


class ProfileForm(StyledFormMixin, forms.ModelForm):
    email = forms.EmailField(required=False, help_text="Where alert emails are sent.")

    class Meta:
        model = Profile
        fields = ["currency", "timezone", "monthly_budget", "alert_threshold", "spike_alerts", "email_alerts"]
        widgets = {
            "monthly_budget": money_widget(),
            "alert_threshold": forms.NumberInput(attrs={"min": 10, "max": 100, "step": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = self.instance.user.email
        self.order_fields(["email", "currency", "timezone", "monthly_budget", "alert_threshold",
                           "spike_alerts", "email_alerts"])

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.user.pk).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("email_alerts") and not cleaned.get("email"):
            self.add_error("email", "Add an email address to receive email alerts.")
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit)
        user = profile.user
        if user.email != self.cleaned_data["email"]:
            user.email = self.cleaned_data["email"]
            user.save(update_fields=["email"])
        return profile


class ExpenseFilterForm(StyledFormMixin, UserCategoryMixin, forms.Form):
    q = forms.CharField(required=False, label="Search", widget=forms.TextInput(attrs={"placeholder": "Search…"}))
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False)
    payment_method = forms.ChoiceField(
        choices=[("", "Any method"), *Expense.PaymentMethod.choices], required=False, label="Method",
    )
    start = forms.DateField(required=False, label="From", widget=DateInput())
    end = forms.DateField(required=False, label="To", widget=DateInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].empty_label = "All categories"

    def filter(self, queryset):
        if not self.is_valid():
            return queryset
        data = self.cleaned_data
        if data["q"]:
            queryset = queryset.filter(Q(description__icontains=data["q"]) | Q(notes__icontains=data["q"]))
        if data["category"]:
            queryset = queryset.filter(category=data["category"])
        if data["payment_method"]:
            queryset = queryset.filter(payment_method=data["payment_method"])
        if data["start"]:
            queryset = queryset.filter(date__gte=data["start"])
        if data["end"]:
            queryset = queryset.filter(date__lte=data["end"])
        return queryset
