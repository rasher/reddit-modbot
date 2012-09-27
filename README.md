# About

Reddit modbot is a relatively lightweight script for automating reddit moderating tasks. It was written as a simpler alternative to [AutoModerator by Deimos](https://github.com/Deimos/AutoModerator).

## Advantages

 * Does not require a database or other semi-complicated setup.
 * Runs continously to avoid startup penalty
 * Defining rules is fairly simple due to simple rules files format
 * Automatically updates rules when you edit/add/remove them on disk
 * Will never re-evaluate an item, which saves time

## Limitations

 * Built with single-subreddit usage in mind. Though this could likely be fixed without too many changes.
 * Rules files are not as flexible as AutoModerator rules
 * All rules are regex, which makes matching numbers slightly convoluted
 * Will never re-evaluate an item, which means it's not really possible to react to items getting downvoted or reported.

# Getting started

Requirements (both available in pypi):
 * [inotifyx](http://www.alittletooquiet.net/software/inotifyx/)
 * [PRAW](https://github.com/praw-dev/praw)

Run it like this:

modbot.py -r /path/to/rules/dir mysubreddit

Additionally, you may pass in the username and password for your reddit user.

## Writing rules files

A rules file is a file ending in .rule, placed in the rules dir.

For every item the bot inspects, it will try to match it against each rule, in order by filename of each rule. If a rule matches, no further rules will be applied.

A rules file contains any number of line of the form "Key: value". After these lines, you may include a rule body, which should be preceded by a blank line. The purpose of this will be described later.

The value of a rule is a regular expression that will be applied to the given value of the item in question (case-insensitively).

Rule lines in the header of the rule, starting with a # character are ignored. The order of rule lines is ignored.

The header lines describe what conditions the comment or post much fullfil to match the rule - or which actions to take. Possible conditions are:

<table>
    <tr>
        <th>Field</th>
        <th>Description</th>
    </tr>
    <tr><td>Username</td><td>name of the author</td></tr>
    <tr><td>Numreports</td><td>number of reports (this is not too useful currently)</td></tr>
    <tr><td>Domain</td><td>domain of the post</td></tr>
    <tr><td>Title</td><td>title of post</td></tr>
    <tr><td>Upvotes</td><td>number of upvotes</td></tr>
    <tr><td>Downvotes</td><td>number of downvotes</td></tr>
    <tr><td>Score</td><td>upvotes-downvotes</td></tr>
    <tr><td>Type</td><td>'comment' or 'submission'</td></tr>
    <tr><td>Body</td><td>content of comment or self-post</td></tr>
    <tr><td>Bodylength</td><td>length of body</td></tr>
    <tr><td>Dayhour</td><td>time of submission on the form Tue-19 in UTC</td></tr>
</table>

In addition to any number of these, you should include a line named "Actions",
with the value being a comma seperated list of actions to take when the rule
matches. Possible actions are:

<table>
<tr>
<th>Action</th>
<th>Description>
</tr>
<tr><td>upvote</td><td>upvote the item</td></tr>
<tr><td>log</td><td>write an entry to the rulelogger logging logger</td></tr>
<tr><td>spam</td><td>mark the item as spam</td></tr>
<tr><td>remove</td><td>remove the item (but don't mark as spam)</td></tr>
<tr><td>approve</td><td>approve the item</td></tr>
<tr><td>respond</td><td>post a distinguished comment, using the body of the rule as a template, using new style python string formatting with the objects "rule" and "thing" available. See below for an example.</td></tr>
<tr><td>messagemods</td><td>message the mods of the subreddit, using the rule body.</td></tr>
<tr><td>beep</td><td>write a BEL character to the terminal</td></tr>
<tr><td>messageauthor</td><td>message the author, using the rule body as template.</td></tr>
<tr><td>report</td><td>report the item</td></tr>
<tr><td>none</td><td>do nothing</td></tr>
<tr><td>linkflair:flairclass:flairtext</td><td>set the linkflair class "flairclass" and text "flairtext" on the item</td></tr>
</table>

## Rule examples

```
Domain: (quickmeme.com|qkme.me|memegenerator.net|weknowmemes.com)
Actions: log,spam,respond

Please do not submit memes to this subreddit.

***

I am an automated bot - please [contact the mods](http://www.reddit.com/message/compose?to=%2Fr%2Fmysubreddit) if you believe I made a mistake.
```

This rules matches any post submitted from a number of meme sites and posts a comment in the thread, as well as marks the submission as spam to train the spam filter.

```
Type: comment
Body: digg
Actions: log,messagemods
Description: Burn the witch!
Subject: Someone mentioned digg

User /u/{thing.author.name} in [this comment]({thing.permalink}?context=3) (thread *{thing.submission.title}*)

***

{thing.body}
```

This rule will match any comment including the word "digg" and alert the mods. Note the use of Python string formatting to include the object's content and a permalink. "thing" is either a Comment or Submission object as defined by the praw library (<https://github.com/praw-dev/praw>).

The "Description" line is not used, but simply there as a human-readable explanation.
