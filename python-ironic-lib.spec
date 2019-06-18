%global pyver 2

%global pyver_bin python%{pyver}
%global pyver_sitelib %python%{pyver}_sitelib
%global pyver_install %py%{pyver}_install
%global pyver_build %py%{pyver}_build

%{!?upstream_version: %global upstream_version %{version}}

%global srcname ironic-lib
%global sum A common library to be used by various projects in the Ironic ecosystem

Name:           python-%{srcname}
Version:        XXX
Release:        XXX
Summary:        %{sum}

License:        ASL 2.0
URL:            http://pypi.python.org/pypi/%{srcname}
Source0:        %{srcname}-%{version}.tar.gz

BuildArch:      noarch

%description
A common library to be used by various projects in the Ironic ecosystem

%package -n     python%{pyver}-%{srcname}
Summary:        %{sum}
%{?python_provide:%python_provide python%{pyver}-%{srcname}}

BuildRequires:  python%{pyver}-devel
BuildRequires:  python%{pyver}-pbr
BuildRequires:  python%{pyver}-setuptools
BuildRequires:  openstack-macros
Requires: python%{pyver}-oslo-concurrency >= 3.25.0
Requires: python%{pyver}-oslo-config >= 2:5.2.0
Requires: python%{pyver}-oslo-i18n >= 3.15.3
Requires: python%{pyver}-oslo-log >= 3.36.0
Requires: python%{pyver}-oslo-serialization >= 2.18.0
Requires: python%{pyver}-oslo-service >= 1.24.0
Requires: python%{pyver}-oslo-utils >= 3.33.0
Requires: python%{pyver}-pbr
Requires: python%{pyver}-requests
Requires: python%{pyver}-six
Requires: python%{pyver}-zeroconf >= 0.19.1

%description -n python%{pyver}-%{srcname}
A common library to be used by various projects in the Ironic ecosystem

%prep
%autosetup -n %{srcname}-%{upstream_version} -p1
%py_req_cleanup

%build
%{pyver_build}

%install
%{pyver_install}

%files -n python%{pyver}-%{srcname}
%license LICENSE
%doc README.rst
%{pyver_sitelib}/*

%changelog

