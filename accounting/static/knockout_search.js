ko.extenders.required = function(target, overrideMessage) {
	target.hasError = ko.observable();
	target.validationMessage = ko.observable();

	function validate(newValue) {
		target.hasError(newValue ? false : true);
		target.validationMessage(target.hasError() ? overrideMessage : "");
	}
 
    //validate whenever the value changes
    target.subscribe(validate);
 
    //return the original observable
    return target;
};

function PolicyViewModel() {
	var self = this;
	self.chosenPolicyData = ko.observable();
	self.policy_number = ko.observable().extend({ required: "Policy number is required" });
	self.date = ko.observable();

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
			success: self.chosenPolicyData,
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
}

$(document).ready(function() {
	$('#date').datepicker({
		format: 'yyyy-mm-dd',
		autoclose: true,
		todayHighlight: true
	});

	ko.applyBindings(new PolicyViewModel());
});
