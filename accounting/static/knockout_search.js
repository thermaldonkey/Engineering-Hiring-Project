// Extension to validate an observable's value is not undefined
ko.extenders.required = function(target, overrideMessage) {
	target.hasError = ko.observable();
	target.validationMessage = ko.observable();

	function validate(newValue) {
		target.hasError(newValue ? false : true);
		target.validationMessage(target.hasError() ? overrideMessage : "");
	}
 
    target.subscribe(validate);
 
    return target;
};
// Base extension to simply add the ability to add errors to an observable
ko.extenders.validated = function(target, enabled) {
	target.hasError = ko.observable();
	target.validationMessage = ko.observable();

	function validate(newValue) {
		target.hasError(false);
		target.validationMessage("");
	}

	target.subscribe(validate);

	return target;
};
// Extension to validate all characters in an observable's value are digits
ko.extenders.numeric = function(target, overrideMessage) {
	target.hasError = ko.observable();
	target.validationMessage = ko.observable();

	function validate(newValue) {
		if(newValue) {
			if(newValue.match(/^\d*$/)) {
				target.hasError(false);
				target.validationMessage("");
			} else {
				target.hasError(true);
				target.validationMessage(overrideMessage);
			}
		}
	}
 
    target.subscribe(validate);

	return target;
};

function PolicyViewModel() {
	var self = this;
	self.chosenPolicyData = ko.observable();
	self.policy_number = ko.observable().extend({ required: "Policy number is required" });
	self.date = ko.observable();
	self.billingSchedules = ko.observableArray(['Annual', 'Two-Pay', 'Quarterly', 'Monthly']);
	self.paymentAmount = ko.observable().extend({ validated: true, numeric: "Must be all digits" });

	self.hasErrors = function() {
		return !!self.policy_number.validationMessage()
	};
	self.verifyForm = function() {
		// I know this doesn't actually execute the validation. I drove myself
		// crazy trying to get presence validations to work, but I couldn't
		// force them to execute here without having them also run on page
		// load.
		if(!self.hasErrors()) {
			self.fetchPolicy()
		}
	};
	self.fetchPolicy = function() {
		$.ajax({
			method: 'POST',
			url: '/find_policy',
			contentType: 'application/json',
			data: ko.toJSON(self),
			success: function(data, text, xhr) {
				self.paymentAmount(null);
				self.chosenPolicyData(data);
			},
			error: function(xhr, text, error) {
				self.displayNewError(xhr);
			},
			dataType: 'json'
		});
	};
	self.displayNewError = function(request) {
		// A 404 tells us the requested policy couldn't be found
		if(request.status == 404) {
			self.policy_number.hasError(true);
			self.policy_number.validationMessage("No policy found with that number");
		}
	};
	self.changeBillingSchedule = function() {
		$.ajax({
			method: 'POST',
			url: '/change_billing_schedule',
			contentType: 'application/json',
			data: ko.toJSON(self.chosenPolicyData),
			success: self.chosenPolicyData,
			dataType: 'json'
		});
	};
	self.makePayment = function() {
		$.ajax({
			method: 'POST',
			url: '/make_payment',
			contentType: 'application/json',
			data: ko.toJSON(self),
			success: function(data, text, xhr) {
				self.paymentAmount(null);
				self.chosenPolicyData(data);
			},
			error: function(xhr, text, error) {
				if(xhr.status == 422) {
					self.paymentAmount.hasError(true);
					self.paymentAmount.validationMessage("Policy must have a named insured to make a payment");
				}
			},
			dataType: 'json'
		});
	};
}

$(document).ready(function() {
	$('#date').datepicker({
		format: 'yyyy-mm-dd',
		autoclose: true,
		todayHighlight: true
	});

	ko.applyBindings(new PolicyViewModel());
});
