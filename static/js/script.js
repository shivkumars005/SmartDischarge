$(document).ready(function() {
    // Set today's date
    $('#discharge_date').val(new Date().toISOString().split('T')[0]);

    // Theme toggle
    const themeToggle = $('#theme-toggle');
    const html = $('html');
    const themeIcon = themeToggle.find('i');

    function setTheme(theme) {
        html.removeClass('light-theme dark-theme').addClass(theme);
        themeIcon.removeClass('fa-moon fa-sun').addClass(theme === 'dark-theme' ? 'fa-sun' : 'fa-moon');
        localStorage.setItem('theme', theme);
    }

    // Load saved theme
    const savedTheme = localStorage.getItem('theme') || 'light-theme';
    setTheme(savedTheme);

    themeToggle.click(function() {
        const currentTheme = html.hasClass('light-theme') ? 'light-theme' : 'dark-theme';
        const newTheme = currentTheme === 'light-theme' ? 'dark-theme' : 'light-theme';
        setTheme(newTheme);
    });

    // Enable/disable buttons
    $('#patient_id').on('input', function() {
        const patientId = $(this).val().trim();
        $('#generate_btn').prop('disabled', !patientId);
        $('#preview_btn').prop('disabled', !patientId);
        $('#patient_preview').addClass('hidden').html('');
        console.log("Entered Patient ID:", patientId);
    });

    // Show notification
    function showNotification(message, isError = false) {
        const notification = $(`
            <div class="fixed bottom-4 right-4 p-4 rounded-lg shadow-lg animate-fade-in ${isError ? 'notification-error' : 'notification-success'}">
                <span>${message}</span>
                <button class="ml-2 text-sm hover:text-opacity-80 dismiss-notification"><i class="fas fa-times"></i></button>
            </div>
        `);
        $('body').append(notification);
        setTimeout(() => {
            notification.addClass('animate-fade-out');
            setTimeout(() => notification.remove(), 500);
        }, 3000);
        notification.find('.dismiss-notification').click(() => {
            notification.addClass('animate-fade-out');
            setTimeout(() => notification.remove(), 500);
        });
    }

    // Preview patient
    $('#preview_btn').click(function(e) {
        e.preventDefault();
        const patientId = $('#patient_id').val().trim();
        if (!patientId) {
            showNotification('Enter a patient ID', true);
            return;
        }

        $('#patient_preview').removeClass('hidden').html('<div class="spinner mr-2"></div>Fetching patient data...');

        $.ajax({
            url: '/preview',
            type: 'POST',
            data: { patient_id: patientId },
            success: function(data) {
                if (data.error) {
                    $('#patient_preview').html(`
                        <div class="alert-error p-4 rounded-lg">
                            <strong>⚠️ Error:</strong> ${data.error}
                        </div>
                    `);
                } else {
                    $('#patient_preview').html(`
                        <div class="p-4 card-secondary rounded-lg">
                            <strong>Patient Details:</strong><br>
                            <p>Name: ${data.name}</p>
                            <p>Sex: ${data.sex}</p>
                            <p>Age: ${data.age}</p>
                            <p>State: ${data.state}</p>
                            <p>Chief Complaint: ${data.chief_complaint}</p>
                            <p>Diagnosis: ${data.disease}</p>
                            <p>Hospital Stay: ${data.stay_duration} days</p>
                            <p>Chronic Condition: ${data.chronic ? 'Yes' : 'No'}</p>
                            <p>Doctor: ${data.doctor_name}</p>
                            <p>Allergies: ${data.allergies}</p>
                            <p>Admission Date: ${data.admission_date}</p>
                            <p>Discharge Date: ${data.discharge_date}</p>
                            <p>Test Reports: ${data.test_reports ? '<a href="/' + data.test_reports + '" target="_blank" class="text-teal-600 hover:underline">View Report</a>' : 'None'}</p>
                            ${data.is_fallback ? "<p class='italic'>Note: Based on similar patient data</p>" : ""}
                        </div>
                    `);
                }
            },
            error: function() {
                $('#patient_preview').html(`
                    <div class="alert-error p-4 rounded-lg">
                        <strong>⚠️ Error:</strong> Failed to fetch patient data.
                    </div>
                `);
            }
        });
    });

    // Generate summary
    $('#generate_btn').click(function(e) {
        e.preventDefault();
        const patientId = $('#patient_id').val().trim();
        if (!patientId) {
            showNotification('Enter a patient ID', true);
            return;
        }

        $('#result').removeClass('hidden').html('<div class="spinner mr-2"></div><span class="text-gray-600 dark:text-gray-400">Generating summary...</span>');

        $.ajax({
            url: '/generate',
            type: 'POST',
            data: {
                patient_id: patientId,
                detail_level: $('input[name="detail_level"]:checked').val(),
                doctor_notes: $('#doctor_notes').val(),
                discharge_date: $('#discharge_date').val()
            },
            success: function(data) {
                console.log("Response:", data);
                $('#result').html('');
                if (data.error) {
                    $('#result').html(`<div class="alert-error p-4 rounded-lg"><strong>⚠️ Error:</strong> ${data.error}</div>`);
                } else {
                    $('#result').html(`
                        <div class="alert-success p-4 rounded-lg card">
                            <strong>✅ Discharge Summary</strong>
                            ${data.summary.is_fallback ? "<p class='mt-2 italic'>Note: Generated based on similar patient data</p>" : ""}
                            <p class="mt-2"><strong>Chief Complaint:</strong> ${data.summary.chief_complaint}</p>
                            <p class="mt-2"><strong>History of Present Illness:</strong> ${data.summary.hpi}</p>
                            <p class="mt-2"><strong>Past History:</strong> ${data.summary.past_history}</p>
                            <p class="mt-2"><strong>Social History:</strong> ${data.summary.social_history}</p>
                            <p class="mt-2"><strong>Allergies:</strong> ${data.summary.allergies}</p>
                            <p class="mt-2"><strong>Physical Exam:</strong> ${data.summary.physical_exam}</p>
                            <p class="mt-2"><strong>Laboratory Data:</strong> ${data.summary.lab_data}</p>
                            <p class="mt-2"><strong>Hospital Course:</strong> ${data.summary.hospital_course}</p>
                            <p class="mt-2"><strong>Condition:</strong> ${data.summary.condition}</p>
                            <p class="mt-2"><strong>Diagnoses:</strong> ${data.summary.diagnosis}</p>
                            <p class="mt-2"><strong>Medications:</strong> ${data.summary.medications}</p>
                            <p class="mt-2"><strong>Diet:</strong> ${data.summary.diet}</p>
                            <p class="mt-2"><strong>Activity:</strong> ${data.summary.activity}</p>
                            <p class="mt-2"><strong>Follow-Up:</strong> ${data.summary.follow_up}</p>
                            <p class="mt-2"><strong>Instructions:</strong> ${data.summary.discharge_instructions}</p>
                            <p class="mt-2"><strong>AI Notes:</strong> ${data.summary.ai_notes}</p>
                            <p class="mt-2"><strong>Admission Date:</strong> ${data.summary.admission_date}</p>
                            <p class="mt-2"><strong>Discharge Date:</strong> ${data.summary.discharge_date}</p>
                            <p class="mt-2"><strong>Doctor:</strong> ${data.summary.doctor_name}</p>
                            <button class="copy-summary-btn inline-block mt-4 bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 transition"><i class="fas fa-copy mr-2"></i>Copy Summary</button>
                            <a href="/download/${data.pdf_file}" class="inline-block mt-4 button px-4 py-2 rounded-lg transition"><i class="fas fa-download mr-2"></i>Download PDF</a>
                        </div>
                    `);

                    // Attach click event to Copy Summary button
                    $('.copy-summary-btn').click(function() {
                        const summaryText = `Chief Complaint: ${data.summary.chief_complaint}\nHPI: ${data.summary.hpi}\nPast History: ${data.summary.past_history}\nSocial History: ${data.summary.social_history}\nAllergies: ${data.summary.allergies}\nPhysical Exam: ${data.summary.physical_exam}\nLab Data: ${data.summary.lab_data}\nHospital Course: ${data.summary.hospital_course}\nCondition: ${data.summary.condition}\nDiagnoses: ${data.summary.diagnosis}\nMedications: ${data.summary.medications}\nDiet: ${data.summary.diet}\nActivity: ${data.summary.activity}\nFollow-Up: ${data.summary.follow_up}\nInstructions: ${data.summary.discharge_instructions}\nAI Notes: ${data.summary.ai_notes}\nAdmission: ${data.summary.admission_date}\nDischarge: ${data.summary.discharge_date}\nDoctor: ${data.summary.doctor_name}`;
                        navigator.clipboard.writeText(summaryText).then(() => {
                            showNotification('Summary copied to clipboard!');
                        }).catch(err => {
                            console.error('Failed to copy text: ', err);
                            showNotification('Failed to copy summary.', true);
                        });
                    });
                }
            },
            error: function(xhr, status, error) {
                console.log("AJAX Error:", status, error);
                $('#result').html(`<div class="alert-error p-4 rounded-lg"><strong>⚠️ Error:</strong> Failed to generate summary. Please try again.</div>`);
            },
            timeout: 60000
        });
    });

    // Form submission (optional, kept for compatibility)
    $('#summary_form').submit(function(e) {
        e.preventDefault();
        $('#generate_btn').click();
    });

    // Handle add patient form submission
    $('#add_patient_form').submit(function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        $.ajax({
            url: '/add_patient',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(data) {
                if (data.error) {
                    showNotification(`Failed to add patient: ${data.error}`, true);
                } else {
                    showNotification(data.message);
                    setTimeout(() => {
                        window.location.href = data.redirect;
                    }, 2000);
                }
            },
            error: function(xhr, status, error) {
                console.log("AJAX Error:", status, error);
                showNotification('Failed to add patient. Please try again.', true);
            }
        });
    });

    // Handle test report upload form submission
    $('#upload_test_report_form').submit(function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        $.ajax({
            url: '/upload_test_report',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(data) {
                if (data.error) {
                    showNotification(`Failed to upload test report: ${data.error}`, true);
                } else {
                    showNotification(data.message);
                    $('#upload_test_report_form')[0].reset();
                }
            },
            error: function(xhr, status, error) {
                console.log("AJAX Error:", status, error);
                showNotification('Failed to upload test report. Please try again.', true);
            }
        });
    });

    // Handle load more button for pagination
    $(document).on('click', '#load-more', function() {
        const nextPage = $(this).data('next-page');
        $.ajax({
            url: '/view_database',
            type: 'GET',
            data: { page: nextPage, ajax: true },
            success: function(data) {
                if (data.error) {
                    showNotification(`Failed to load more patients: ${data.error}`, true);
                    return;
                }
                const tbody = $('#patient-table-body');
                data.patients.forEach(patient => {
                    const row = `
                        <tr class="border-t animate-fade-in">
                            <td class="p-2 sm:p-3">${patient.PatientID}</td>
                            <td class="p-2 sm:p-3">${patient.Name}</td>
                            <td class="p-2 sm:p-3">${patient.Sex}</td>
                            <td class="p-2 sm:p-3">${patient.State}</td>
                            <td class="p-2 sm:p-3">${patient.GeneralHealth}</td>
                            <td class="p-2 sm:p-3">${patient.HasChronicCondition ? 'Yes' : 'No'}</td>
                            <td class="p-2 sm:p-3">${patient.HospitalStayDuration}</td>
                            <td class="p-2 sm:p-3">${patient.RiskCategory}</td>
                            <td class="p-2 sm:p-3">${patient.DoctorName}</td>
                            <td class="p-2 sm:p-3">${patient.Allergies}</td>
                            <td class="p-2 sm:p-3">${patient.ChiefComplaint}</td>
                            <td class="p-2 sm:p-3">${patient.AdmissionDate}</td>
                            <td class="p-2 sm:p-3">${patient.DischargeDate}</td>
                            <td class="p-2 sm:p-3">
                                ${patient.TestReports ? `<a href="/${patient.TestReports}" target="_blank" class="text-teal-600 hover:underline">View Report</a>` : 'None'}
                            </td>
                        </tr>
                    `;
                    tbody.append(row);
                });
                if (!data.has_more) {
                    $('#load-more').remove();
                } else {
                    $('#load-more').data('next-page', data.next_page);
                }
            },
            error: function(xhr, status, error) {
                console.log("AJAX Error:", status, error);
                showNotification('Failed to load more patients. Please try again.', true);
            }
        });
    });
});