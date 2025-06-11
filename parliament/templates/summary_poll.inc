<div class="summary_poll"><span {% if hl %}class="hl"{% endif %}>Was this summary helpful and accurate?</span><br>
    <button class="button hollow small" onclick="OP.summary_poll_vote(3, '{{summary.id}}', '{{ summary|escapejs }}')">Yes</button>
    <button class="button hollow small" onclick="OP.summary_poll_vote(2, '{{summary.id}}', '{{ summary|escapejs }}')">Sort of</button>
    <button class="button hollow small" onclick="OP.summary_poll_vote(1, '{{summary.id}}', '{{ summary|escapejs }}')">No</button></div>

<script type="text/javascript">
OP.summary_poll_vote = function(vote, summaryId, description) {
    const pollDiv = document.querySelector('.summary_poll');
    fetch('/summaries/poll/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'vote=' + encodeURIComponent(vote) + '&summary_id=' + encodeURIComponent(summaryId)
    })

    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok for poll vote');
        }
        var message = "Thanks for your feedback!";
        if (vote < 3) {
            var maillink = '<a href="mailto:michael@openparliament.ca?subject=' + encodeURIComponent('Summary feedback: ' + description + " " + summaryId) + '">email</a>';
            message += " I'd appreciate an " + maillink + " to point out what you didn't like, or write below:";
            pollDiv.innerHTML = `
                <span>${message}</span><br>
                <textarea id="summary_feedback_text" rows="3" style="width: 100%; max-width: 600px; display: inline-block; margin: 5px 0;" placeholder="What was inaccurate or unhelpful?"></textarea><br>
                <button id="submit_summary_feedback" class="button hollow" style="margin: 0">Send</button>
            `;

            document.getElementById('submit_summary_feedback').addEventListener('click', function() {
                const feedbackText = document.getElementById('summary_feedback_text').value;
                if (feedbackText.trim() === '') {
                    alert('Please enter your feedback.');
                    return;
                }

                // Send the feedback
                fetch('/summaries/feedback/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: 'summary_id=' + encodeURIComponent(summaryId) + '&feedback=' + encodeURIComponent(feedbackText)
                        + '&vote=' + encodeURIComponent(vote) + '&description=' + encodeURIComponent(description)
                })
                .then(feedbackResponse => {
                    if (!feedbackResponse.ok) {
                        throw new Error('Network response was not ok for feedback submission');
                    }
                    pollDiv.innerHTML = '<span>Thank you for sending your feedback!</span>';
                })
                .catch(error => {
                    pollDiv.innerHTML = '<span>Sorry, there was an error submitting your feedback. Please try again later.</span>';
                    throw error;
                });
            });
        } else {
            // Just show thank you message for 'Yes' vote
            pollDiv.innerHTML = '<span>' + message + '</span>';
        }
    })
    .catch(error => {
        pollDiv.innerHTML = '<span>Sorry, there was an error recording your vote. Please try again later.</span>';
        throw error;
    });
}
</script>