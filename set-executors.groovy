import jenkins.model.Jenkins
Jenkins.getInstance().setNumExecutors(2)
Jenkins.getInstance().save()
println("Successfully configured 2 executors.")
