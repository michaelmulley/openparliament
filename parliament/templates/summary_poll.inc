<div class="summary_poll"><span {% if hl %}class="hl"{% endif %}>Was this summary helpful and accurate?</span><br>
    <button class="button hollow small" onclick="OP.summary_poll_vote(3, '{{summary.id}}', '{{ summary|escapejs }}')">Yes</button>
    <button class="button hollow small" onclick="OP.summary_poll_vote(2, '{{summary.id}}', '{{ summary|escapejs }}')">Sort of</button>
    <button class="button hollow small" onclick="OP.summary_poll_vote(1, '{{summary.id}}', '{{ summary|escapejs }}')">No</button></div>

<script type="text/javascript">
OP.summary_poll_vote = function(vote, summaryId, description) {
    fetch('/summaries/poll/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'vote=' + encodeURIComponent(vote) + '&summary_id=' + encodeURIComponent(summaryId)
    })
    .then(function() {
        var message = "Thanks for your feedback!";
        if (vote < 3) {
            var maillink = '<a href="mailto:michael@openparliament.ca?subject=' + encodeURIComponent('Summary feedback: ' + description + " " + summaryId) + '">email</a>';
            message = message + " We'd appreciate an " + maillink + " to point out inaccuracies or problems.";
        }
        document.querySelector('.summary_poll').innerHTML = '<span>' + message + '</span>';
    });
}
</script>