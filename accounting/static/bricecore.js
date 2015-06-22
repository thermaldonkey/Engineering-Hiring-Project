function PolicyViewModel() {
	var self = this;
	self.chosenPolicyData = ko.observable();
	self.policy_number = ko.observable();
	self.date = ko.observable();

	self.fetchPolicy = function() {
		$.ajax({
			method: 'POST',
			url: '/find_policy',
			contentType: 'application/json',
			data: ko.toJSON(self),
			success: self.chosenPolicyData,
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
