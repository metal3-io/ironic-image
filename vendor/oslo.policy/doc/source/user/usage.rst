=======
 Usage
=======

To use oslo.policy in a project, import the relevant module. For
example::

    from oslo_policy import policy

Migrating to oslo.policy
========================

Applications using the incubated version of the policy code from Oslo aside
from changing the way the library is imported, may need to make some extra
changes.

Incorporating oslo.policy tooling
---------------------------------

The ``oslo.policy`` library offers a generator that projects can use to render
sample policy files, check for redundant rules or policies, among other things.
This is a useful tool not only for operators managing policies, but also
developers looking to automate documentation describing the projects default
policies.

This part of the document describes how you can incorporate these features into
your project. Let's assume we're working on an OpenStack-like project called
``foo``. Policies for this service are registered in code in a common module of
the project.

First, you'll need to expose a couple of entry points in the project's
``setup.cfg``::

    [entry_points]
    oslo.policy.policies =
        foo = foo.common.policies:list_rules

    oslo.policy.enforcer =
        foo = foo.common.policy:get_enforcer

The ``oslo.policy`` library uses the project namespace to call ``list_rules``,
which should return a list of ``oslo.policy`` objects, either instances of
``RuleDefault`` or ``DocumentedRuleDefault``.

The second entry point allows ``oslo.policy`` to generate complete policy from
overrides supplied by an existing policy file on disk. This is useful for
operators looking to supply a policy file to Horizon or for security compliance
complete with overrides important to that deployment. The ``get_enforcer``
method should return an instance of ``oslo.policy.policy:Enforcer``. The
information passed into the constructor of ``Enforcer`` should resolve any
overrides on disk. An example for project ``foo`` might look like the
following::

    from oslo_config import cfg
    from oslo_policy import policy

    from foo.common import policies

    CONF = cfg.CONF
    _ENFORCER = None

    def get_enforcer():
        CONF([], project='foo')
        global _ENFORCER
        if not _ENFORCER:
            _ENFORCER = policy.Enforcer(CONF)
            _ENFORCER.register_defaults(policies.list_rules())
        return _ENFORCER

Please note that if you're incorporating this into a project that already uses
``oslo.policy`` in some form or fashion, this might need to be changed to fit
that project's structure accordingly.

Next, you can create a configuration file for generating policies specifically
for project ``foo``. This file could be called ``foo-policy-generator.conf``
and it can be kept under version control within the project::

    [DEFAULT]
    output_file = etc/foo/policy.yaml.sample
    namespace = foo

If project ``foo`` uses tox, this makes it easier to create a specific tox
environment for generating sample configuration files in ``tox.ini``::

    [testenv:genpolicy]
    commands = oslopolicy-sample-generator --config-file etc/foo/foo-policy-generator.conf

Changes to Enforcer Initialization
----------------------------------

The ``oslo.policy`` library no longer assumes a global configuration object is
available. Instead the :py:class:`oslo_policy.policy.Enforcer` class has been
changed to expect the consuming application to pass in an ``oslo.config``
configuration object.

When using policy from oslo-incubator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    enforcer = policy.Enforcer(policy_file=_POLICY_PATH)

When using oslo.policy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    from oslo_config import cfg
    CONF = cfg.CONF
    enforcer = policy.Enforcer(CONF, policy_file=_POLICY_PATH)

Registering policy defaults in code
===================================

A project can register policy defaults in their code which brings with it some
benefits.

* A deployer only needs to add a policy file if they wish to override the
  project defaults.

* Projects can use Enforcer.authorize to ensure that a policy check is being
  done against a registered policy. This can be used to ensure that all
  policies used are registered. The signature of Enforcer.authorize matches
  Enforcer.enforce.

* Projects can register policies as `DocumentedRuleDefault` objects, which
  require a method and path of the corresponding policy. This helps policy
  readers understand which path maps to a particular policy ultimately
  providing better documentation.

* A sample policy file can be generated based on the registered policies
  rather than needing to manually maintain one.

* A policy file can be generated which is a merge of registered defaults and
  policies loaded from a file. This shows the effective policy in use.

* A list can be generated which contains policies defined in a file which match
  defaults registered in code. These are candidates for removal from the file
  in order to keep it small and understandable.

How to register
---------------

::

    from oslo_config import cfg
    CONF = cfg.CONF
    enforcer = policy.Enforcer(CONF, policy_file=_POLICY_PATH)

    base_rules = [
        policy.RuleDefault('admin_required', 'role:admin or is_admin:1',
                           description='Who is considered an admin'),
        policy.RuleDefault('service_role', 'role:service',
                           description='service role'),
    ]

    enforcer.register_defaults(base_rules)
    enforcer.register_default(policy.RuleDefault('identity:create_region',
                                                 'rule:admin_required',
                                                 description='helpful text'))

To provide more information about the policy, use the `DocumentedRuleDefault`
class::

    enforcer.register_default(
        policy.DocumentedRuleDefault(
            'identity:create_region',
            'rule:admin_required',
            'helpful text',
            [{'path': '/regions/{region_id}', 'method': 'POST'}]
        )
    )

The `DocumentedRuleDefault` class inherits from the `RuleDefault`
implementation, but it must be supplied with the `description` attribute in
order to be used. In addition, the `DocumentedRuleDefault` class requires a new
`operations` attributes that is a list of dictionaries. Each dictionary must
have a `path` and a `method` key. The `path` should map to the path used to
interact with the resource the policy protects. The `method` should be the HTTP
verb corresponding to the `path`. The list of `operations` can be supplied with
multiple dictionaries if the policy is used to protect multiple paths.

Naming policies
---------------

Policy names are an integral piece of information in understanding how
OpenStack's policy engine works. Developers protect APIs using policy names.
Operators use policy names to override policies in their deployment. Having
consistent policy names across OpenStack services is essential to providing a
pleasant user experience. The following rules are guidelines to help you, as a
developer, build unique and descriptive policy names.

Service types
~~~~~~~~~~~~~

Policy names should be specific about the service that uses them. The service
type should also follow a known standard, which is the `service-types authority
<https://service-types.openstack.org/service-types.json>`_.  Using an existing
standard avoids confusing users by reusing an established reference. For
example, instead of using `keystone` as the service in a policy name, you
should use `identity`, since it is not specific to one implementation. It's
also more specific about the functionality provided by the service instead of
having readers maintain a mental mapping between service code name and
functionality it provides.

Resources and subresources
~~~~~~~~~~~~~~~~~~~~~~~~~~

Users may interact with resources exposed by a service's API. You should
include the name of a resource in the policy name, and it should be singular.
For example, policies that protect the user API should use `identity:user`,
instead of `identity:users`.

Some services might have subresources. For example, a fixed IP address could be
considered a subresource of an IP address. You should separate open-form
compound words with a hyphen and not an underscore. This spacing convention
maintains consistency with spacing used in the service types authority. For
example, use `ip-address` instead of `ip_address`. Having more than one way to
separate compound words within a single convention is confusing and prone to
accidentally introducing inconsistencies.

Resource names should be minimalist and contain only characters needed to
describe the resource. Extra information should be omitted from the resource
altogether. Use `agent` instead of `os-agents`, even if the URL path of the
resource uses `/os-agents`.

Actions and subactions
~~~~~~~~~~~~~~~~~~~~~~

Actions are specific things that users can do to resources. Typical actions are
`create`, `get`, `list`, `update`, and `delete`. These action definitions are
independent of the HTTP method used to implement their underlying API, which is
intentional. This independence is important because two different services may
implement the same action using two different HTTP methods. For example, use
`compute:server:list` as a policy name for listing servers instead of
`compute:server:get_all` or `compute:server:get-all`. Using `all` in the policy
name itself implies returning every possible entity when the actual response
may be filtered based on the user's authority. In other words, list servers for
a domain administrator managing many different projects within that domain
could be very different from a member of a project listing servers owned by a
single project.

Some services have the ability to list resources with greater detail. Depending
on the context, those additional details might be sensitive in nature and
require more strict RBAC permissions than `list`. In this case, use
`compute:server:list-detail` as opposed to `compute:server:detail`. By using a
compound word, we're being more descriptive about what the `detail` actually
means.

Subactions are optionally available for you to add clarity about resource
actions. For example, `compute:server:resize:confirm` is an example of how you
can compound an action (resize) with a subaction (confirm) to explicitly name a
policy.

Actions that are open form compound words should use hyphens instead of
underscores for spacing. This spacing is consistent with the service types
authority and resource names for open form compound words. For example, use
`compute:server:resize-state` instead of `compute:server:resize_state`.

Resource Attributes
~~~~~~~~~~~~~~~~~~~

Resource attributes may be used in policy names, and are entirely optional. If
you need to include the attribute of a resource in the name, you should place
it after the resource or subresource portion. For example, use
`compute:flavor:private:list` to name a policy for listing all private flavors.

Putting it all together
~~~~~~~~~~~~~~~~~~~~~~~

Now that you know what services types, resources, attributes, and actions are
within the context of policy names, let establish the order you should use
them. Policy names should increase in detail as you read it. This results in
the following syntax::

  <service-type>:<resource>[:<subresource>][:<attribute>]:<action>[:<subaction>]

You should delimit each segment of the name with a colon (:). The following are
examples for existing OpenStack APIs::

  identity:user:list
  block-storage:volume:extend
  compute:server:resize:confirm
  compute:flavor:private:list
  network:ip-address:fixed-ip-address:create

Setting scope
-------------

The `RuleDefault` and `DocumentedRuleDefault` objects have an attribute
dedicated to the intended scope of the operation called `scope_types`. This
attribute can only be set at rule definition and never overridden via a policy
file. This variable is designed to save the scope at which a policy should
operate. During enforcement, the information in `scope_types` is compared to
the scope of the token used in the request. It is designed to match the
available token scopes available from keystone, which are `system`, `domain`,
and `project`. The examples highlighted here will show the usage with system
and project APIs. Setting `scope_types` to anything but these three values is
unsupported.

For example, a policy that is used to protect a resource tracked in a project
should require a project-scoped token. This can be expressed with `scope_types`
as follows::

    policy.DocumentedRuleDefault(
        name='service:create_foo',
        check_str='role:admin',
        scope_types=['project'],
        description='Creates a foo resource',
        operations=[
            {
                'path': '/v1/foos/',
                'method': 'POST'
            }
        ]
    )

A policy that is used to protect system-level resources can follow the same
pattern::

    policy.DocumentedRuleDefault(
        name='service:update_bar',
        check_str='role:admin',
        scope_types=['system'],
        description='Updates a bar resource',
        operations=[
            {
                'path': '/v1/bars/{bar_id}',
                'method': 'PATCH'
            }
        ]
    )

The `scope_types` attribute makes sure the token used to make the request is
scoped properly and passes the `check_str`. This is powerful because it allows
roles to be reused across different authorization levels without compromising
APIs. For example, the `admin` role in the above example is used at the
project-level and the system-level to protect two different resources. If we
only checked that the token contained the `admin` role, it would be possible
for a user with a project-scoped token to access a system-level API.

Developers incorporating `scope_types` into OpenStack services should be
mindful of the relationship between the API they are protecting with a policy
and if it operates on system-level resources or project-level resources.

Sample file generation
----------------------

In setup.cfg of a project using oslo.policy::

    [entry_points]
    oslo.policy.policies =
        nova = nova.policy:list_policies

where list_policies is a method that returns a list of policy.RuleDefault
objects.

Run the oslopolicy-sample-generator script with some configuration options::

    oslopolicy-sample-generator --namespace nova --output-file policy-sample.yaml

or::

    oslopolicy-sample-generator --config-file policy-generator.conf

where policy-generator.conf looks like::

    [DEFAULT]
    output_file = policy-sample.yaml
    namespace = nova

If output_file is omitted the sample file will be sent to stdout.

Merged file generation
----------------------

This will output a policy file which includes all registered policy defaults
and all policies configured with a policy file. This file shows the effective
policy in use by the project.

In setup.cfg of a project using oslo.policy::

    [entry_points]
    oslo.policy.enforcer =
        nova = nova.policy:get_enforcer

where get_enforcer is a method that returns a configured
oslo_policy.policy.Enforcer object. This object should be setup exactly as it
is used for actual policy enforcement, if it differs the generated policy file
may not match reality.

Run the oslopolicy-policy-generator script with some configuration options::

    oslopolicy-policy-generator --namespace nova --output-file policy-merged.yaml

or::

    oslopolicy-policy-generator --config-file policy-merged-generator.conf

where policy-merged-generator.conf looks like::

    [DEFAULT]
    output_file = policy-merged.yaml
    namespace = nova

If output_file is omitted the file will be sent to stdout.

List of redundant configuration
-------------------------------

This will output a list of matches for policy rules that are defined in a
configuration file where the rule does not differ from a registered default
rule. These are rules that can be removed from the policy file with no change
in effective policy.

In setup.cfg of a project using oslo.policy::

    [entry_points]
    oslo.policy.enforcer =
        nova = nova.policy:get_enforcer

where get_enforcer is a method that returns a configured
oslo_policy.policy.Enforcer object. This object should be setup exactly as it
is used for actual policy enforcement, if it differs the generated policy file
may not match reality.

Run the oslopolicy-list-redundant script::

    oslopolicy-list-redundant --namespace nova

or::

    oslopolicy-list-redundant --config-file policy-redundant.conf

where policy-redundant.conf looks like::

    [DEFAULT]
    namespace = nova

Output will go to stdout.

Testing default policies
========================

Developers need to reliably unit test policies used to protect APIs. Having
robust unit test coverage increases confidence that changes won't negatively
affect user experience. This document is intended to help you understand
historical context behind testing practices you may find in your service. More
importantly, it's going to describe testing patterns you can use to increase
confidence in policy testing and coverage.

History
-------

Before the ability to register policies in code, developers maintained policies
in a policy file, which included all policies used by the service. Developers
maintained policy files within the project source code, which contained the
default policies for the service.

Once it became possible to register policies in code, policy files became
irrelevant because you could generate them. Generating policy files from code
made maintaining documentation for policies easier and allowed for a single
source of truth. Registering policies in code also meant testing no longer
required a policy file, since the default policies were in the service itself.

At this point, it is important to note that policy enforcement requires an
authorization context based on the user making the request (e.g., is the user
allowed to do the operation they're asking to do). Within OpenStack, this
authorization context is relayed to services by the token used to call an API,
which comes from an OpenStack identity service. In its purest form, you can
think of authorization context as the roles a user has on a project, domain, or
system. Services can feed the authorization context into policy enforcement,
which determines if a user is allowed to do something.

The coupling between the authorization context, ultimately the token, and the
policy enforcement mechanism raises the bar for effectively testing policies
and APIs. Service developers want to ensure the functionality specific to their
service works, and not dwell on the implementation details of an authorization
system. Additionally, they want to keep unit tests lightweight, as opposed to
requiring a separate system to issue tokens for authorization, crossing the
boundary of unit testing to integration testing.

Because of this, you typically see one of two approaches taken concerning
policies and test code across OpenStack services.

One approach is to supply a policy file specifically for testing that overrides
the sample policy file or default policies in code. This file contains mostly
policies without proper check strings, which relaxes the authorization enforced
by the service using oslo.policy. Without proper check strings, it's possible
to access APIs without building context objects or using tokens from an
identity service.

The other approach is to mock policy enforcement to succeed unconditionally.
Since developers are bypassing the code within the policy engine, supplying a
proper authorization context doesn't have an impact on the APIs used in the
test case.

Both methods let developers focus on validating the domain-specific
functionality of their service without needing to understand the intricacies of
policy enforcement. Unfortunately, bypassing API authorization testing comes at
the expense of introducing gaps where the default policies may break
unexpectedly with new changes. If the tests don't assert the default behavior,
it's likely that seemingly simple changes negatively impact users or operators,
regardless of that being the intent of the developer.

Testing policies
----------------

Fortunately, you can test policies without needing to deal with tokens by using
context objects directly, specifically a RequestContext object. Chances are
your service is already using these to represent information from middleware
that sits in front of the API. Using context for authorization strikes a
perfect balance between integration testing and exercising just enough
authorization to ensure policies sufficiently protect APIs. The oslo.policy
library also accepts context objects and automatically translates properties to
values used when evaluating policy, which makes using them even more natural.

To use RequestContext objects effectively, you need to understand the policy
under test. Then, you can model a context object appropriately for the test
case. The idea is to build a context object to use in the request that either
fails or passes policy enforcement. For example, assume you're testing a
default policy like the following:

::

    from oslo_config import cfg

    CONF = cfg.CONF
    enforcer = policy.Enforcer(CONF, policy_file=_POLICY_PATH)

    enforcer.register_default(
        policy.RuleDefault('identity:create_region', 'role:admin')
    )

Enforcement here is straightforward in that a user with a role called ``admin``
may access this API. You can model this in a request context by setting these
attributes explicitly:

::

    from oslo_context import context

    context = context.RequestContext()
    context.roles = ['admin']

Depending on how your service deploys the API in unit tests, you can either
provide a fake context as you supply the request, or mock the return value of
the context to return the one you've built.

You can also supply scope information for policies with complex check strings
or the use of scope types. For example, consider the following default policy:

::

    from oslo_config import cfg

    CONF = cfg.CONF
    enforcer = policy.Enforcer(CONF, policy_file=_POLICY_PATH)

    enforcer.register_default(
        policy.RuleDefault('identity:create_region', 'role:admin',
        scope_types=['system'])
    )

We can model it using the following request context object, which includes
scope:

::

    from oslo_context import context

    context = context.RequestContext()
    context.roles = ['admin']
    context.system_scope = 'all'

Note that ``all`` is a unique system scope target that signifies the user is
authorized to operate on the deployment system. Conversely, the following is an
example of a context modeling a project-scoped token:

::

    import uuid
    from oslo_context import context

    context = context.RequestContext()
    context.roles = ['admin']
    context.project_id = uuid.uuid4().hex

The significance here is the difference between administrator authorization on
the deployment system and administrator authorization on a project.
