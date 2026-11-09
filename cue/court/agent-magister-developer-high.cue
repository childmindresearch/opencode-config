package court

Agents: "magister-developer-high": _courtDeveloper & {
	description: "High-effort Court developer; default for ordinary tasks, complex work or uncertain implementation."
	model:       "\(_modelDefs.highEffort.provider)/\(_modelDefs.highEffort.id)"
}
