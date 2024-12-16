import random
import jsonschema._utils
import jsonschema.benchmarks
import jsonschema.exceptions
import jsonschema.tests
import wx
from jsf import JSF

from .model import HumanModel, NeuroAction
from .view import HumanView
from .api import *

def action_id_generator():
    '''Generate a unique ID for an action.'''

    i = 0
    while True:
        yield f'action_{i}'
        i += 1

class HumanController:

    def __init__(self, app: wx.App):
        self.app = app
        self.model = HumanModel()
        self.view = HumanView(app, self.model)
        self.api = NeuroAPI()

        self.id_generator = action_id_generator()

        self.inject()

        self.api.start()

    def run(self):
        self.view.show()
        self.app.MainLoop()

    def inject(self):
        '''Inject methods into the view and API.'''

        self.api.on_startup = self.on_startup
        self.api.on_context = self.on_context
        self.api.on_actions_register = self.on_actions_register
        self.api.on_actions_unregister = self.on_actions_unregister
        self.api.on_actions_force = self.on_actions_force
        self.api.on_action_result = self.on_action_result
        self.api.on_shutdown_ready = self.on_shutdown_ready
        self.api.on_unknown_command = self.on_unknown_command
        self.api.log = self.view.log
        self.api.log_info = self.view.log_info
        self.api.log_warning = self.view.log_warning
        self.api.log_error = self.view.log_error
        self.api.log_network = self.view.log_network

        self.view.on_execute = self.on_view_execute
        self.view.on_delete_action = self.on_view_delete_action
        self.view.on_send_actions_reregister_all = self.on_view_send_actions_reregister_all
        self.view.on_send_shutdown_graceful = self.on_view_send_shutdown_graceful
        self.view.on_send_shutdown_graceful_cancel = self.on_view_send_shutdown_graceful_cancel
        self.view.on_send_shutdown_immediate = self.on_view_send_shutdown_immediate

    def on_any_command(self, cmd: Any):
        '''Callback for any command received from the API.'''

        # if self.view.is_focus_on_receive_checked():
        #     self.view.focus()

    def on_startup(self, cmd: StartupCommand):
        '''Handle the startup command.'''

        self.view.log('startup command received.')
        self.model.clear_actions()
        self.view.clear_actions()
    
    def on_context(self, cmd: ContextCommand):
        '''Handle the context command.'''

        self.view.log('context command received.')
        self.view.log_context(cmd.message, silent=cmd.silent)

    def on_actions_register(self, cmd: ActionsRegisterCommand):
        '''Handle the actions/register command.'''

        self.view.log('actions/register command received.')

        for action in cmd.actions:

            # Check if an action with the same name already exists
            if self.model.has_action(action.name):
                self.view.log_warning(f'Error: Action "{action.name}" already exists. Ignoring.')
                continue
            
            self.model.add_action(action)
            wx.CallAfter(self.view.add_action, action)
            self.view.log(f'Action registered: {action.name}')
            self.view.log_context(f'{action.name}: {action.description}')

    def on_actions_unregister(self, cmd: ActionsUnregisterCommand):
        '''Handle the actions/unregister command.'''

        self.view.log('actions/unregister command received.')

        for name in cmd.action_names:
            if not self.model.has_action(name):
                self.view.log_info(f'Info: Action "{name}" does not exist.')

            self.model.remove_action_by_name(name)
            self.view.remove_action_by_name(name)
            self.view.log(f'Action unregistered: {name}')

    def on_actions_force(self, cmd: ActionsForceCommand):
        '''Handle the actions/force command.'''

        if cmd.state is not None and cmd.state != '':
            self.view.log_context(cmd.state, ephemeral=cmd.ephemeral_context)
        else:
            self.view.log_info('Info: actions/force command contains no state.')

        self.view.log_context(cmd.query, ephemeral=cmd.ephemeral_context)

        if self.view.is_ignore_actions_force_checked():
            self.view.log('actions/force command received, but ignored.')
            return
        
        # Check if all actions exist
        if not all(self.model.has_action(name) for name in cmd.action_names):
            self.view.log_warning('Warning: actions/force with invalid actions received. Discarding.\nInvalid actions: ' + ', '.join(name for name in cmd.action_names if not self.model.has_action(name)))
            return

        self.view.log('actions/force command received.')

        if self.view.is_auto_send_checked():
            self.view.log('Automatically sending random action.')
            actions = [action for action in self.model.actions if action.name in cmd.action_names]
            action = random.choice(actions)

            if action.schema is None:
                self.send_action(next(self.id_generator), action.name, None)
            else:
                faker = JSF(action.schema)
                sample = faker.generate()
                self.send_action(next(self.id_generator), action.name, json.dumps(sample))
                
        else:
            wx.CallAfter(self.view.force_actions, cmd.state, cmd.query, cmd.ephemeral_context, cmd.action_names)

    def on_action_result(self, cmd: ActionResultCommand):
        '''Handle the action/result command.'''

        self.view.log('action/result command received: ' + ('success' if cmd.success else 'failure'))
        
        if cmd.message is not None:
            self.view.log_context(cmd.message)
        elif cmd.success:
            self.view.log_info('Info: Successful action result contains no message.')
        else:
            self.view.log_warning('Warning: Failed action result contains no message.')

        wx.CallAfter(self.view.on_action_result, cmd.success, cmd.message)

    def on_shutdown_ready(self, cmd: ShutdownReadyCommand):
        '''Handle the shutdown/ready command.'''

        self.view.log('shutdown/ready command received.')
        self.view.log_warning('Warning: This command is not in the official API specification.')

    def on_unknown_command(self, json_cmd: Any):
        '''Handle an unknown command.'''

        self.view.log_warning(f'Warning: Unknown command received: {json_cmd['command']}')

    def send_action(self, id: str, name: str, data: str | None):
        '''Send an action command to the API.'''

        self.view.log(f'Sending action: {name}')
        self.api.send_action(id, name, data)

        self.view.disable_actions() # Disable the actions until the result is received

    def send_actions_reregister_all(self):
        '''Send an actions/reregister_all command to the API.'''

        self.view.log('Sending actions/reregister_all command.')
        self.view.log_warning('Warning: This command is not in the official API specification.')
        self.api.send_actions_reregister_all()

    def on_view_execute(self, action: NeuroAction):
        '''Handle an action execution request from the view.'''

        if not action.schema:
            self.send_action(next(self.id_generator), action.name, None) # No schema, so send the action immediately
            return
        
        # If there is a schema, open a dialog to get the data
        result = self.view.show_action_dialog(action)
        if result is None:
            return # User cancelled the dialog
        
        self.send_action(next(self.id_generator), action.name, result)

    def on_view_delete_action(self, name: str):
        '''Handle a request to delete an action from the view.'''

        self.model.remove_action_by_name(name)
        self.view.remove_action_by_name(name)

        self.view.log(f'Action deleted: {name}')

    def on_view_send_actions_reregister_all(self):
        '''Handle a request to send an actions/reregister_all command from the view.'''

        self.model.clear_actions()
        wx.CallAfter(self.view.clear_actions)
        self.send_actions_reregister_all()

    def on_view_send_shutdown_graceful(self):
        '''Handle a request to send a shutdown/graceful command with wants_shutdown=true from the view.'''

        self.view.log('Sending shutdown/graceful command.')
        self.view.log_warning('Warning: This command is not in the official API specification.')
        self.api.send_shutdown_graceful(True)

    def on_view_send_shutdown_graceful_cancel(self):
        '''Handle a request to send a shutdown/graceful with wants_shutdown=false command from the view.'''

        self.view.log('Sending shutdown/graceful command.')
        self.view.log_warning('Warning: This command is not in the official API specification.')
        self.api.send_shutdown_graceful(False)

    def on_view_send_shutdown_immediate(self):
        '''Handle a request to send a shutdown/immediate command from the view.'''

        self.view.log('Sending shutdown/immediate command.')
        self.view.log_warning('Warning: This command is not in the official API specification.')
        self.api.send_shutdown_immediate()
