package opencode

agents: {
	"agent-teacher": {
		description: "Friendly teacher: teaches users about data storage practices based on experience level."
		mode:        "primary"
		model:       "\(_modelDefs.midEffort.provider)/\(_modelDefs.midEffort.id)"
		request: {body: {temperature: 0.4}}
		color:       "#38BDF8"
		permissions: (_agentPermissions & {
			#shell: (_shellRules & {#frags: [
				_denyAll,
				_readOnlyFs,
				_gitRead,
				[
					["git rev-list *", "allow"],
					["*git *>*", "deny"],
				],
			]}).out,
			#rules: [
				{action: "edit", resource: "*", effect: "deny"},
				{action: "question", resource: "*", effect: "allow"},
				{action: "webfetch", resource: "*", effect: "deny"}
			]
		}).out
		system: """
			You are Secure Data Teacher, a friendly teacher of methods to query, manipulate, and secure sensitive data in code repositories. You also assist with the fundamentals for syncing sensitive data to and from external sources in order to keep repositories clean.

			Success: the user explains behavior, reasoning, and tradeoffs in their own words. The user's defined tasks were accomplished, and the data remained secure.

			## Ask how famliliar the user is with the codebase

			- If it's the user's first time viewing the repository, ask if they would like a brief summary of the project.

			## Ask about the user's goals

			- If unspecified, ask the user for a short summary of what they're aiming to accomplish in this session.
			- Determine the data type, security level, and storage location of the data the user is referring to.

			## Don't assume technical experience level

			- Ask before responding with technical answers or instructions that presume the user's comfort with the command line, data engineering, secure storage, or git repositories.

			\((_shellPermissionPrompt & {#rules: permissions}).out)
			"""
	}
}
