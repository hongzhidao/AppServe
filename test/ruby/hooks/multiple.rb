require 'securerandom'

on_worker_boot do
    File.write("./cookie_worker_boot.#{SecureRandom.hex}", "worker booted")
end

on_worker_shutdown do
    File.write("./cookie_worker_shutdown.#{SecureRandom.hex}", "shutdown")
end
