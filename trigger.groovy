import jenkins.model.Jenkins
def job = Jenkins.getInstance().getItemByFullName("java-app-deploy")
if (job != null) {
    job.scheduleBuild2(0)
    println("Build triggered successfully from init script.")
}
new File("/var/lib/jenkins/init.groovy.d/trigger.groovy").delete()
