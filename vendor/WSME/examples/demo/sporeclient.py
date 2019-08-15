import spyre
import spyre.middleware


class CTypeHeader(spyre.middleware.Middleware):
    def __call__(self, env):
        env.setdefault('spore.headers', [])
        env['spore.headers'].extend([
            ('Accept', 'application/json'),
            ('Content-Type', 'application/json')
        ])


demo = spyre.new_from_url('http://127.0.0.1:8080/ws/api.spore')
demo.enable(CTypeHeader)
demo.enable('format.Json')

print demo.helloworld().content
