BILL_SUMMARY_FROM_SPEECHES = """You will be provided with a transcript of the speeches at the reading of a bill in the Canadian House of Commons. Based on the speeches, please write a 2-4 sentence summary of the bill.

The people speaking are members of different parties and have different points of view. You should summarize the bill in a neutral way, without adopting any party's point of view.

Respond with only the summary, no extra headings or comments.
"""

BILL_READING_INSTRUCTIONS_PARTY = """You will be provided with a transcript of the speeches by members of one political party at the reading of a bill in the Canadian House of Commons. Please summarize the party's position on the bill. 

Before each speech, the name of the member speaking is provided. Most paragraphs begin with a URL for that paragraph in [square brackets]. (URLs are relative, that's fine, use them as-is.) Speeches are separated with "----".

Provide 1-4 bullet points summarizing the party's position on the bill. Return your summary in JSON. (Include only the JSON object for the summary in your response.)

Use the following structure:
[
    {
        "headline": "2-6 word phrase establishing the topic of this point. Use sentence case, not Title Case.",
        "source_paragraph_url": "Relative URL, copied exactly from the transcript provided, to the paragraph where the discussion that best supports this point begins.",
        "summary": "1-3 sentences on this summary point"
    }
]

Here's an example:
[
    {
        "headline": "Supports bill C-95",
        "source_paragraph_url": "/para/h38f",
        "summary": "The Bloc supported the bill, emphasizing the need to enhance transparency and build trust between victims and the justice system."
    },
    {
        "headline": "Quebec's leadership",
        "source_paragraph_url": "/para/72HHd",
        "summary": "Members noted Quebec's initiatives, such as specialized courts and electronic monitoring, as models in improving victim protection and restoring trust in the justice system."
    },
    {
        "headline": "Focus on violence against women",
        "source_paragraph_url": "/para/9KKp4d",
        "summary": "Christine Guy-Marcil highlighted an increase in femicide and domestic violence. She argued that Parliament has a responsibility to try and reverse the trend, that concrete action is slow in coming, but that this bill is a step to improve victims' experience with the justice system and start rebuilding trust."
    }
]

"""