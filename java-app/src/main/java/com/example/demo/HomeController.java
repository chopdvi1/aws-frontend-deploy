package com.example.demo;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import java.lang.management.ManagementFactory;
import com.sun.management.OperatingSystemMXBean;

@Controller
public class HomeController {

    @GetMapping("/")
    public String index(Model model) {
        model.addAttribute("javaVersion", System.getProperty("java.version"));
        model.addAttribute("osName", System.getProperty("os.name"));
        model.addAttribute("osArch", System.getProperty("os.arch"));
        
        OperatingSystemMXBean osBean = (OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
        long totalMemory = osBean.getTotalMemorySize() / (1024 * 1024); // MB
        long freeMemory = osBean.getFreeMemorySize() / (1024 * 1024); // MB
        long usedMemory = totalMemory - freeMemory;
        double cpuLoad = osBean.getCpuLoad() * 100;
        
        // Handle negative value if system is still loading CPU stats
        if (cpuLoad < 0) {
            cpuLoad = 0.0;
        }
        
        model.addAttribute("totalMemory", totalMemory);
        model.addAttribute("usedMemory", usedMemory);
        model.addAttribute("freeMemory", freeMemory);
        model.addAttribute("cpuLoad", String.format("%.2f", cpuLoad));
        model.addAttribute("availableProcessors", osBean.getAvailableProcessors());

        return "index";
    }
}
