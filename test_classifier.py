"""Regression tests for the MoveInSync review triage classifier."""
import unittest

from moveinsync_ratings_monitor import classify, classify_all


class ClassifierRegressionTests(unittest.TestCase):
    def assertPrimary(self, text, expected):
        theme, _owner = classify(text)
        self.assertEqual(theme, expected, msg=f"Unexpected primary theme for: {text!r}")

    def test_substring_change_is_not_launch_failure(self):
        self.assertPrimary("I cannot change address in the app", "UI / release / usability")

    def test_completely_is_not_transport_delay(self):
        self.assertNotEqual(classify("The app is completely broken")[0], "Transport operations / driver / route")

    def test_frustrating_is_not_rating_prompt(self):
        self.assertNotEqual(classify("This is a frustrating experience")[0], "Rating prompts / notifications")

    def test_assigning_is_not_sign_in(self):
        self.assertNotEqual(classify("Cabs are not assigning properly")[0], "OTP / login / session")

    def test_mic_requires_word_boundary(self):
        self.assertNotEqual(classify("The application is basic")[0], "Policy / permission prompts")

    def test_installer_error_gets_specific_theme(self):
        self.assertPrimary("It says app was not installed through Play Store", "Install verification / Play Store error")

    def test_generic_not_installed_is_access_signal(self):
        self.assertPrimary("Sometimes I open the app and it says not installed", "Install verification / Play Store error")

    def test_otp_delivery_problem(self):
        self.assertPrimary("The app is not sending OTP", "OTP / login / session")

    def test_repeated_logout(self):
        self.assertPrimary("It logs out every time", "OTP / login / session")

    def test_logged_in_phrase(self):
        self.assertPrimary("I cannot stay logged in for more than a day", "OTP / login / session")

    def test_helpdesk_unreachable(self):
        self.assertPrimary("The helpdesk is unreachable", "Support / escalation")

    def test_customer_service_phrase(self):
        self.assertPrimary("Worst customer service and no response", "Support / escalation")

    def test_forced_rating(self):
        self.assertPrimary("Forcing me to give a rating after every ride", "Rating prompts / notifications")

    def test_no_skip_feedback(self):
        self.assertPrimary("There is no option to skip feedback after each trip", "Rating prompts / notifications")

    def test_generic_safety_check_is_not_safety_incident(self):
        self.assertNotEqual(classify("It asks me to confirm seat belt safety before showing OTP")[0], "Safety / security")

    def test_actual_unsafe_concern_is_safety(self):
        self.assertPrimary("Female employees feel unsafe during the night ride", "Safety / security")

    def test_unable_to_open_is_launch_failure(self):
        self.assertPrimary("Unable to open the app on my phone", "App launch / crash")

    def test_hang_is_launch_failure(self):
        self.assertPrimary("The app keeps hanging when I open it", "App launch / crash")

    def test_slow_tracker_is_eta_theme(self):
        self.assertPrimary("The cab tracker is useless and does not update on time", "ETA / tracking / location")

    def test_routing_complaint_is_transport_ops(self):
        self.assertPrimary("The route is too long and drivers arrive late", "Transport operations / driver / route")

    def test_booking_status_problem(self):
        self.assertPrimary("The app says trip not booked even after confirmation", "Booking / schedule / roster")

    def test_policy_prompt_detected(self):
        self.assertPrimary("It asks me to accept transport policy every time", "Policy / permission prompts")

    def test_multi_label_captures_secondary_issue(self):
        matches = [name for name, _ in classify_all("OTP never arrives and the helpdesk gives no response")]
        self.assertIn("OTP / login / session", matches)
        self.assertIn("Support / escalation", matches)

    def test_unmatched_short_review_is_neutral_other(self):
        self.assertEqual(classify("Worst app")[0], "No specific detail / other")

    def test_missing_information_is_booking_signal(self):
        self.assertPrimary("Not able to provide information and keeping employees uninformed", "Booking / schedule / roster")

    def test_missing_address_is_booking_signal(self):
        self.assertPrimary("Stupid app showing no address", "Booking / schedule / roster")

    def test_missing_trip_details_is_booking_signal(self):
        self.assertPrimary("Only good for initial one month don't show any details anymore", "Booking / schedule / roster")

    def test_address_change_friction_is_ui_signal(self):
        self.assertPrimary("Changing an address requires too much effort", "UI / release / usability")

    def test_qr_boarding_feature_comparison_is_ui_signal(self):
        self.assertPrimary("Not as good as another app, scanning QR to board the cab was cool", "UI / release / usability")

    def test_grammatical_variation_in_update_timing_is_reliability(self):
        self.assertPrimary("Very bad, this app is not updated every thing on time", "General app reliability / performance")

    def test_comparative_reliability_signal_is_detected(self):
        self.assertPrimary("EFMEM is more reliable", "General app reliability / performance")

    def test_broken_app_explicitly_not_working_is_reliability(self):
        self.assertPrimary("Very bad app not work", "General app reliability / performance")


if __name__ == "__main__":
    unittest.main(verbosity=2)
